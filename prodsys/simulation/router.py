from __future__ import annotations

from collections.abc import Callable
import random
from typing import List, TYPE_CHECKING, Generator, Optional, Union, Dict, Set, Tuple
from dataclasses import dataclass, field

import logging
import time

import simpy

logger = logging.getLogger(__name__)

from simpy import events

from prodsys.simulation import resources, store
from prodsys.simulation import request
from prodsys.simulation.process import ReworkProcess


if TYPE_CHECKING:
    from prodsys.simulation import resources, product, sink, auxiliary, process
    from prodsys.factories import (
        resource_factory,
        sink_factory,
        auxiliary_factory,
        product_factory,
        source_factory
    )
    from prodsys.control import routing_control_env
    from prodsys.models import product_data
    from prodsys.simulation.product import Locatable
    # from prodsys.factories.source_factory import SourceFactory


def get_env_from_requests(requests: List[request.Request]) -> simpy.Environment:
    """
    Returns the environment from a list of requests.

    Args:
        requests (List[request.Request]): The requests.

    Returns:
        simpy.Environment: The environment.
    """
    if not requests:
        raise ValueError("No requests found to retrieve an environment from.")
    if requests[0].product:
        return requests[0].product.env
    else:
        return requests[0].auxiliary.env


def get_item_to_transport(
    request_for_transport: Union[request.Request, request.AuxiliaryRequest],
) -> Union[product.Product, auxiliary.Auxiliary]:
    """
    Returns the item to transport from a request.

    Args:
        request_for_transport (Union[request.Request, request.AuxiliaryRequest]): The request.

    Returns:
        Union[product.Product, auxiliary.Auxiliary]: The item to transport.
    """
    if isinstance(request_for_transport, request.AuxiliaryRequest):
        return request_for_transport.auxiliary
    return request_for_transport.product


@dataclass(frozen=True)
class ResourceCompatibilityKey:
    """Key for the resource compatibility lookup table."""

    product_type: str
    process_signature: str

    @classmethod
    def from_request(cls, request: request.Request) -> "ResourceCompatibilityKey":
        """Create a key from a request."""
        product_type = request.product.product_data.product_type
        process_signature = request.process.get_process_signature()
        return cls(product_type=product_type, process_signature=process_signature)


@dataclass(frozen=True)
class TransportCompatibilityKey:
    """Key for the transport compatibility lookup table."""

    origin_id: str
    target_id: str
    process_signature: str

    @classmethod
    def from_request(
        cls, request: request.TransportResquest
    ) -> "TransportCompatibilityKey":
        """Create a key from a transport request."""
        origin_id = request.origin.data.ID
        target_id = request.target.data.ID
        process_signature = request.process.get_process_signature()
        return cls(
            origin_id=origin_id,
            target_id=target_id,
            process_signature=process_signature,
        )


class Router:
    """
    Base class for all routers.

    Args:
        resource_factory (resource_factory.ResourceFactory): The resource factory of the production system.
        sink_factory (sink_factory.SinkFactory): The sink factory of the production system.
        routing_heuristic (Callable[[List[resources.Resource]], resources.Resource]): The routing heuristic to be used, needs to be a callable that takes a list of resources and returns a resource.
    """

    def __init__(
        self,
        resource_factory: resource_factory.ResourceFactory,
        sink_factory: sink_factory.SinkFactory,
        auxiliary_factory: auxiliary_factory.AuxiliaryFactory,
        routing_heuristic: Callable[[List[request.Request]], None],
        product_factory: Optional[product_factory.ProductFactory] = None,
        source_factory: Optional[source_factory.SourceFactory] = None,
    ):
        self.resource_factory: resource_factory.ResourceFactory = resource_factory
        self.sink_factory: sink_factory.SinkFactory = sink_factory
        self.auxiliary_factory: auxiliary_factory.AuxiliaryFactory = auxiliary_factory
        self.routing_heuristic: Callable[[List[request.Request]], None] = (
            routing_heuristic
        )
        self.product_factory: Optional[product_factory.ProductFactory] = product_factory
        self.source_factory: Optional[source_factory.SourceFactory] = source_factory

        # Precomputed compatibility tables
        self.production_compatibility: Dict[
            ResourceCompatibilityKey, List[tuple[resources.ProductionResource, process.PROCESS_UNION]]
        ] = {}
        self.transport_compatibility: Dict[
            TransportCompatibilityKey, List[Tuple[resources.TransportResource, process.PROCESS_UNION]]
        ] = {}
        self.rework_compatibility: Dict[
            Tuple[str, str], List[process.ReworkProcess]
        ] = {}
        self.reachability_cache: Dict[Tuple[str, str], bool] = {}
        self.route_cache: Dict[Tuple[str, str, str], request.TransportResquest] = {}

        # Initialize compatibility tables

    def precompute_compatibility_tables(self):
        """
        Precompute compatibility tables for resources and processes.
        This method runs at initialization time to create lookup tables
        that will speed up resource selection during simulation.
        """
        start_time = time.time()
        logger.info("Precomputing resource compatibility tables...")

        # Get dummy product for testing
        dummy_products: dict[str, product.Product] = {}
        for source in self.source_factory.sources: 
            product_type = source.product_data.product_type
            dummy_products[product_type] = self._create_dummy_product(source.product_data)

        # Precompute production resource compatibility
        for product_type, dummy_product in dummy_products.items():
            while True:
                dummy_product.set_next_production_process()
                if dummy_product.next_prodution_process is None:
                    break
                for resource in self.resource_factory.get_production_resources():
                    requested_process = dummy_product.next_prodution_process
                    dummy_production_request = request.Request(
                            process=requested_process, product=dummy_product, resource=resource
                        )
                    for offered_process in resource.processes:
                        # Test if this process matches the request
                        if offered_process.matches_request(dummy_production_request):
                            key = ResourceCompatibilityKey(
                                product_type=product_type,
                                process_signature=requested_process.get_process_signature(),
                            )
                            if key not in self.production_compatibility:
                                self.production_compatibility[key] = []
                            self.production_compatibility[key].append((resource, offered_process))

        # Precompute transport resource compatibility and reachability
        for product_type, dummy_product in dummy_products.items():
            requested_process = dummy_product.transport_process
            for transport_resource in self.resource_factory.get_transport_resources():
                for offered_process in transport_resource.processes:
                    # For each possible origin-target pair
                    all_locations = (
                        self.resource_factory.resources + self.sink_factory.sinks + self.source_factory.sources
                    )
                    for origin in all_locations:
                        for target in all_locations:
                            # Create a dummy request to test matching
                            dummy_product.current_locatable = origin

                            dummy_transport_request = request.TransportResquest(
                                process=requested_process,
                                product=dummy_product,
                                resource=transport_resource,
                                origin=origin,
                                target=target,
                            )

                            # Test if this transport process can handle this origin-target pair
                            if offered_process.matches_request(dummy_transport_request):
                                key = TransportCompatibilityKey(
                                    origin_id=origin.data.ID,
                                    target_id=target.data.ID,
                                    process_signature=requested_process.get_process_signature(),
                                )
                                if key not in self.transport_compatibility:
                                    self.transport_compatibility[key] = []
                                self.transport_compatibility[key].append((transport_resource, offered_process))

                                # Cache reachability information
                                self.reachability_cache[
                                    (origin.data.ID, target.data.ID)
                                ] = True

                                # Cache the route
                                route_key = (
                                    origin.data.ID,
                                    target.data.ID,
                                    offered_process.get_process_signature(),
                                )
                                if route_key not in self.route_cache:
                                    self.route_cache[route_key] = dummy_transport_request

        # Precompute rework process compatibility
        # for rework_proc in self.resource_factory.process_factory.processes:
        #     if not isinstance(rework_proc, offered_process.ReworkProcess):
        #         continue

        #     for prod_proc in self.resource_factory.process_factory.processes:
        #         if isinstance(prod_proc, offered_process.ReworkProcess):
        #             continue

        #         # For each product type
        #         for product_type, dummy_product in dummy_products.items():
        #             dummy_rework_request = request.ReworkRequest(
        #                 failed_process=prod_proc, product=dummy_product
        #             )

        #             if rework_proc.matches_request(dummy_rework_request):
        #                 key = (product_type, prod_proc.get_process_signature())
        #                 if key not in self.rework_compatibility:
        #                     self.rework_compatibility[key] = []
        #                 self.rework_compatibility[key].append(rework_proc)

        logger.info(
            f"Precomputation completed in {time.time() - start_time:.2f} seconds"
        )
        logger.info(
            f"Production compatibility table contains {len(self.production_compatibility)} entries"
        )
        logger.info(
            f"Transport compatibility table contains {len(self.transport_compatibility)} entries"
        )
        logger.info(
            f"Reachability cache contains {len(self.reachability_cache)} entries"
        )
        logger.info(
            f"Rework compatibility table contains {len(self.rework_compatibility)} entries"
        )

    def _create_dummy_product(self, product_data: product_data.ProductData) -> product.Product:
        """
        Create a dummy product for compatibility testing.

        Args:
            product_type: The product type

        Returns:
            A dummy product instance
        """
        return self.product_factory.create_product(
            product_data=product_data, router=self
        )

    def route_product_to_production_resource(
        self, product: product.Product
    ) -> Generator[Optional[request.Request]]:
        """
        Routes a product to perform the next process by assigning a production resource, that performs the process, to the product
        and assigning a transport resource to transport the product to the next process.

        Args:
            product (product.Product): The product.

        Returns:
            Generator[Tuple[request.Request, request.TransportResquest]]: A generator that yields when the product is routed.
        """
        potential_production_requests = self.get_possible_production_requests(product)
        if not potential_production_requests:
            raise ValueError(
                f"No possible production resources found for product {product.product_data.ID} and process {product.next_prodution_process.process_data.ID}."
            )
        potential_transport_requests: List[request.Request] = []

        potential_transport_requests = self.get_possible_transport_requests(
            potential_production_requests
        )
        if not potential_transport_requests:
            raise ValueError(
                f"No possible transport resources found for product {product.product_data.ID} and process {product.next_prodution_process.process_data.ID} to reach any destinations from resource {product.current_locatable.data.ID}."
            )
        possible_production_requests = self.get_reachable_production_requests(
            potential_production_requests, potential_transport_requests
        )

        env = get_env_from_requests(potential_transport_requests)
        routed_production_request = yield env.process(
            self.get_routed_production_request(possible_production_requests)
        )
        return routed_production_request

    def get_input_queue_state_change_events(
        self, possible_requests: List[request.Request]
    ) -> List[events.Event]:
        """
        Returns the state change events of the input queues of the resources of the requests.

        Args:
            possible_requests (List[request.Request]): The requests.

        Returns:
            List[events.Event]: The state change events of the input queues of the resources of the requests.
        """
        possible_resources: List[resources.ProductionResource] = []
        for request in possible_requests:
            if not request.resource in possible_resources and isinstance(
                request.resource, resources.ProductionResource
            ):
                possible_resources.append(request.resource)
        input_queue_get_events = []
        for resource in possible_resources:
            for queue in resource.input_queues:
                input_queue_get_events.append(queue.state_change)
        stores: list[store.Store] = []
        for request in possible_requests:
            if not isinstance(request.resource, store.Store):
                continue
            stores.append(request.resource)
        for store_instance in stores:
            input_queue_get_events.append(store_instance.state_change)
        return input_queue_get_events

    def get_routed_production_request(
        self, possible_production_requests: List[request.Request]
    ) -> Generator[Optional[request.Request]]:
        env = get_env_from_requests(possible_production_requests)
        while True:
            production_requests: List[request.Request] = (
                self.get_requests_with_non_blocked_resources(
                    possible_production_requests
                )
            )
            if production_requests:
                break
            logger.debug(
                {
                    "ID": possible_production_requests[0].product.product_data.ID,
                    "sim_time": env.now,
                    "event": f"Waiting for free resources.",
                }
            )
            yield events.AnyOf(
                env,
                self.get_input_queue_state_change_events(possible_production_requests),
            )
            logger.debug(
                {
                    "ID": possible_production_requests[0].product.product_data.ID,
                    "sim_time": env.now,
                    "event": f"Free resources available.",
                }
            )

        self.routing_heuristic(production_requests)
        if not production_requests:
            return
        routed_production_request = production_requests.pop(0)
        chosen_resource: resources.ProductionResource = (
            routed_production_request.resource
        )
        chosen_resource.reserve_internal_input_queues()
        return routed_production_request

    def route_transport_resource_for_item(
        self,
        routed_production_request: Union[
            request.Request, request.AuxiliaryRequest, request.ToTransportRequest
        ],
    ) -> Generator[Optional[request.TransportResquest]]:
        """
        Routes a product to perform the next process by assigning a production resource, that performs the process, to the product
        and assigning a transport resource to transport the product to the next process.

        Args:
            item_to_transport (Union[product.Product, auxiliary.Auxiliary]): The product or auxiliary to transport.
            routed_production_request (Union[request.Request, request.AuxiliaryRequest]): The production request or auxiliary request.

        Returns:
            Generator[Optional[request.TransportResquest]]: A generator that yields when the product is routed.
        """
        item_to_transport = get_item_to_transport(routed_production_request)
        potential_transport_requests: List[request.Request] = (
            self.get_transport_requests_to_target(
                item_to_transport, routed_production_request.resource, {}
            )
        )

        if not potential_transport_requests:
            raise ValueError(
                f"No possible transport resources found for product {item_to_transport.product_data.ID} and process {item_to_transport.next_prodution_process.process_data.ID} to reach any destinations from resource {item_to_transport.current_locatable.data.ID}."
            )

        env = get_env_from_requests(potential_transport_requests)
        while True:
            transport_requests: List[request.TransportResquest] = (
                self.get_requests_with_non_blocked_resources(
                    potential_transport_requests
                )
            )
            if transport_requests:
                break
            logger.debug(
                {
                    "ID": item_to_transport.product_data.ID,
                    "sim_time": env.now,
                    "event": f"Waiting for free resources.",
                }
            )
            yield events.AnyOf(
                env,
                self.get_input_queue_state_change_events(potential_transport_requests),
            )
            logger.debug(
                {
                    "ID": item_to_transport.product_data.ID,
                    "sim_time": env.now,
                    "event": f"Free resources available.",
                }
            )
        if not transport_requests:
            raise ValueError(
                f"No transport requests found for routing of product {item_to_transport.product_data.ID}. Error in Event handling of routing to resources."
            )
        self.routing_heuristic(transport_requests)
        yield env.timeout(0)
        if not transport_requests:
            return
        routed_transport_request = transport_requests.pop(0)
        return routed_transport_request

    def route_product_to_sink(
        self, product: product.Product
    ) -> Generator[Optional[request.TransportResquest]]:
        """
        Routes a product to a sink.

        Args:
            product (product.Product): The product.

        Returns:
            Generator[request.TransportResquest]: A generator that yields when the product is routed to the sink.
        """
        sink = self.get_sink(product.product_data.product_type)
        sink_request = request.ToTransportRequest(product=product, target=sink)
        potential_transport_requests = self.get_possible_transport_requests(
            [sink_request]
        )
        if not potential_transport_requests:
            raise ValueError(
                f"No possible transport resources found for product {product.product_data.ID} to reach any sinks from resource {product.current_locatable.data.ID}."
            )
        env = get_env_from_requests(potential_transport_requests)
        while True:
            transport_requests: List[request.TransportResquest] = (
                self.get_requests_with_non_blocked_resources(
                    potential_transport_requests
                )
            )
            if transport_requests:
                break
            logger.debug(
                {
                    "ID": product.product_data.ID,
                    "sim_time": env.now,
                    "event": f"Waiting for free resources.",
                }
            )
            yield events.AnyOf(
                env,
                self.get_input_queue_state_change_events(potential_transport_requests),
            )
            logger.debug(
                {
                    "ID": product.product_data.ID,
                    "sim_time": env.now,
                    "event": f"Free resources available.",
                }
            )
        if not transport_requests:
            raise ValueError(
                f"No transport requests found for routing of product {product.product_data.ID}. Error in Event handling of routing to resources."
            )
        self.routing_heuristic(transport_requests)
        yield env.timeout(0)
        if not transport_requests:
            return
        routed_transport_request = transport_requests.pop(0)
        for queue in sink.input_queues:
            queue.reserve()
        return routed_transport_request

    def route_product_to_storage(
        self, product: product.Product
    ) -> Generator[request.TransportResquest]:
        """
        Routes a product to the store.

        Args:
            product (product.Product): The product.

        Returns:
            Generator[request.TransportResquest]: A generator that yields when the product is routed to the store.
        """
        resource = product.current_locatable
        external_queues = [
            queue for queue in resource.output_queues if isinstance(queue, store.Store)
        ]
        if not external_queues:
            raise ValueError(
                f"No external queues found for product {product.product_data.ID} to reach any store from resource {product.current_locatable.data.ID}."
            )

        potential_to_transport_requests = []
        for external_queue in external_queues:
            to_transport_request = request.ToTransportRequest(
                product=product, target=external_queue
            )
            potential_to_transport_requests.append(to_transport_request)

        env = get_env_from_requests(potential_to_transport_requests)
        while True:
            to_transport_requests: List[request.ToTransportRequest] = (
                self.get_requests_with_non_blocked_resources(
                    potential_to_transport_requests
                )
            )
            if to_transport_requests:
                break
            logger.debug(
                {
                    "ID": product.product_data.ID,
                    "sim_time": env.now,
                    "event": f"Waiting for free resources for storage.",
                }
            )
            yield events.AnyOf(
                env,
                self.get_input_queue_state_change_events(
                    potential_to_transport_requests
                ),
            )
            logger.debug(
                {
                    "ID": product.product_data.ID,
                    "sim_time": env.now,
                    "event": f"Free resources available for storage.",
                }
            )

        storage_request = random.choice(to_transport_requests)
        storage_request.resource.reserve()
        transport_request = yield env.process(
            self.route_transport_resource_for_item(storage_request)
        )

        return transport_request

    def route_product_from_storage(
        self, product: product.Product, resource: resources.ProductionResource
    ) -> Generator[request.TransportResquest]:
        """
        Routes a product from the store.

        Args:
            product (product.Product): The product.
            resource (resources.ProductionResource): The production resource.

        Returns:
            Generator[request.TransportResquest]: A generator that yields when the product is routed from the store.
        """
        env = product.env
        to_transport_request = request.ToTransportRequest(
            product=product, target=resource
        )
        transport_request = yield env.process(
            self.route_transport_resource_for_item(to_transport_request)
        )
        return transport_request

    def check_store_product(self, product: product.Product) -> bool:
        """
        Decides whether a product is stored in the store.

        Returns:
            bool: If the product is stored in the store.
        """
        resource = product.current_locatable
        external_queues = [
            queue for queue in resource.output_queues if isinstance(queue, store.Store)
        ]
        if not external_queues:
            return False
        internal_queues = [
            queue
            for queue in resource.output_queues
            if not isinstance(queue, store.Store)
        ]
        if all(queue.full for queue in internal_queues):
            return True
        # TODO: implement heuristic for storage
        return random.choice([True, False])

    def get_production_request(
        self, product: product.Product, resource: resources.Resource
    ) -> request.Request:
        """
        Returns a request for the next production process of the product object.

        Returns:
            request.Request: The request for the next production process.
        """
        return request.Request(
            process=product.next_prodution_process,
            product=product,
            resource=resource,
        )

    def get_transport_request(
        self,
        item_to_transport: Union[product.Product, auxiliary.Auxiliary],
        transport_resource: resources.TransportResource,
        target: resources.Resource,
    ) -> request.TransportResquest:
        """
        Returns a request for the next transport process of the product object.

        Returns:
            request.Request: The request for the next transport process.
        """
        return request.TransportResquest(
            process=item_to_transport.transport_process,
            product=item_to_transport,
            resource=transport_resource,
            origin=item_to_transport.current_locatable,
            target=target,
        )

    def route_auxiliary_to_product(
        self, product: product.Product
    ) -> Generator[request.AuxiliaryRequest]:
        """
        Routes an auxiliary to a product.

        Args:
            product (product.Product): The product.

        Returns:
            Generator: A generator that yields when the auxiliary is routed to the product.
        """
        auxiliary_request = request.AuxiliaryRequest(
            product=product, process=product.transport_process
        )
        yield product.env.process(self.get_auxiliary(auxiliary_request))
        yield product.env.timeout(0)
        return auxiliary_request

    def route_auxiliary_to_store(
        self, auxiliary: auxiliary.Auxiliary
    ) -> Generator[request.TransportResquest]:
        """
        Routes an auxiliary to a store.

        Args:
            auxiliary (auxiliary.Auxiliary): The auxiliary.

        Returns:
            Generator: A generator that yields when the auxiliary is routed to the store.
        """
        auxiliary_request = request.AuxiliaryRequest(
            auxiliary=auxiliary,
            process=auxiliary.transport_process,
            resource=auxiliary.storage,
            product=None,
        )
        # transport_request = self.get_transport_request(auxiliary, auxiliary.transport_process, auxiliary.storage)
        env = get_env_from_requests([auxiliary_request])
        transport_request: request.TransportResquest = yield env.process(
            self.route_transport_resource_for_item(auxiliary_request)
        )
        yield env.timeout(0)
        return transport_request

    def get_auxiliary(self, processing_request: request.AuxiliaryRequest) -> Generator:
        possible_auxiliaries = self.get_possible_auxiliaries(processing_request)
        while True:
            free_possible_auxiliaries = self.get_free_auxiliary(possible_auxiliaries)
            # TODO: maybe make heuristic working for selecting auxiliary...
            random.shuffle(free_possible_auxiliaries)
            if free_possible_auxiliaries:
                break
            logger.info(
                {
                    "ID": processing_request.product.product_data.ID,
                    "sim_time": processing_request.product.env.now,
                    "event": f"Waiting for free auxiliary.",
                }
            )
            yield events.AnyOf(
                processing_request.product.env,
                [auxiliary.got_free for auxiliary in possible_auxiliaries],
            )
            logger.info(
                {
                    "ID": processing_request.product.product_data.ID,
                    "sim_time": processing_request.product.env.now,
                    "event": f"Free auxiliary available.",
                }
            )
        routed_auxiliary = free_possible_auxiliaries[0]
        routed_auxiliary.reserve()
        routed_auxiliary.got_free = events.Event(processing_request.product.env)
        routed_auxiliary.current_product = processing_request.product
        processing_request.auxiliary = routed_auxiliary
        processing_request.resource = processing_request.product.current_locatable

    def get_free_auxiliary(
        self, possible_auxiliaries: List[auxiliary.Auxiliary]
    ) -> List[auxiliary.Auxiliary]:
        free_possible_auxiliaries = []
        for auxiliary in possible_auxiliaries:
            if not auxiliary.reserved and auxiliary.current_product is None:
                free_possible_auxiliaries.append(auxiliary)
        return free_possible_auxiliaries

    def get_possible_auxiliaries(
        self, processing_request: request.AuxiliaryRequest
    ) -> List[auxiliary.Auxiliary]:
        possible_auxiliaries = []
        for auxiliary in self.auxiliary_factory.auxiliaries:
            if (
                not auxiliary.data.auxiliary_type
                in processing_request.product.product_data.auxiliaries
            ):
                continue
            if any(
                supported_process.matches_request(processing_request)
                for supported_process in auxiliary.relevant_processes
                + auxiliary.relevant_transport_processes
            ):
                possible_auxiliaries.append(auxiliary)
        return possible_auxiliaries

    def get_possible_production_requests(
        self, product: product.Product
    ) -> List[request.Request]:
        """
        Returns a list of possible production requests with different resources and processes for the next production process of a product.
        Uses precomputed compatibility tables for improved performance.
        """
        possible_requests = []

        # Create a key for lookup
        key = ResourceCompatibilityKey(
            product_type=product.product_data.product_type,
            process_signature=product.next_prodution_process.get_process_signature(),
        )

        # Use the precomputed compatibility table
        compatible_resources_and_processes = self.production_compatibility.get(key, [])

        for resource, process in compatible_resources_and_processes:
            production_request = self.get_production_request(product, resource)
            production_request.set_process(process)
            possible_requests.append(production_request)

        return possible_requests

    def get_reachable_production_requests(
        self,
        production_requests: List[request.Request],
        transport_requests: List[request.TransportResquest],
    ) -> List[request.Request]:
        """
        Returns a list of production requests that are reachable by the transport requests.

        Args:
            production_requests (List[request.Request]): potential production requests
            transport_requests (List[request.Request]): potential transport requests

        Returns:
            List[request.Request]: A list of production requests that are reachable by the transport requests.
        """
        possible_production_resource_ids = set(
            [request.target.data.ID for request in transport_requests]
        )
        return [
            request
            for request in production_requests
            if request.resource.data.ID in possible_production_resource_ids
        ]

    def get_possible_transport_requests(
        self, production_requests: List[request.Request]
    ) -> List[request.TransportResquest]:
        """
        Returns a list of possible transport requests with different resources and processes for the next transport process of a product.

        Args:
            production_request (request.Request): The production request to get the transport request for.

        Returns:
            List[request.TransportResquest]: A list of possible transport requests for the next transport process of the product.
        """
        if any(
            isinstance(production_request, request.ToTransportRequest)
            for production_request in production_requests
        ):
            transport_targets = [request.resource for request in production_requests]
        else:
            transport_target_ids = set(
                [request.resource.data.ID for request in production_requests]
            )
            transport_targets = [
                resource
                for resource in self.resource_factory.resources
                if resource.data.ID in transport_target_ids
            ]
        product = production_requests[0].product

        possible_requests = []
        route_cache = {}

        for transport_target in transport_targets:
            possible_requests += self.get_transport_requests_to_target(
                product, transport_target, route_cache
            )
        return possible_requests

    def get_transport_requests_to_target(
        self,
        item_to_transport: Union[product.Product, auxiliary.Auxiliary],
        target: Locatable,
        route_cache: dict,
    ) -> List[request.TransportResquest]:
        """
        Returns a list of possible transport requests for the item to the target.
        Uses precomputed compatibility tables for improved performance.
        """
        transport_requests = []
        origin = item_to_transport.current_locatable

        # Early check if target is reachable from origin
        if not self.reachability_cache.get((origin.data.ID, target.data.ID), False):
            return []

        # For each transport process available to the item
        transport_process = item_to_transport.transport_process
        process_signature = transport_process.get_process_signature()

        # Look up compatible resources in precomputed table
        key = TransportCompatibilityKey(
            origin_id=origin.data.ID,
            target_id=target.data.ID,
            process_signature=process_signature,
        )

        compatible_resources_and_processes = self.transport_compatibility.get(key, [])

        # Get cached route if available
        route_key = (origin.data.ID, target.data.ID, process_signature)
        cached_route = self.route_cache.get(route_key)

        for compatible_resource, compatible_process in compatible_resources_and_processes:
            # Create a transport request
            transport_request = self.get_transport_request(
                item_to_transport, compatible_resource, target
            )

            # Set process and copy route from cache if available
            transport_request.set_process(compatible_process)
            if cached_route:
                transport_request.copy_cached_routes(cached_route)
            transport_requests.append(transport_request)

        return transport_requests

    def get_requests_with_non_blocked_resources(
        self, requests: List[request.Request]
    ) -> List[request.Request]:
        """
        Returns a list of requests with non-blocked resources.

        Args:
            requests (List[request.Request]): A list of requests.

        Returns:
            List[request.Request]: A list of requests with non-blocked resources.
        """
        for request in requests:
            if not isinstance(request.resource, resources.ProductionResource):
                continue
        return [
            request
            for request in requests
            if isinstance(request.resource, resources.TransportResource)
            or (
                isinstance(request.resource, resources.ProductionResource)
                and not any(q.full for q in request.resource.input_queues)
            )
            or (isinstance(request.resource, store.Store) and not request.resource.full)
        ]

    def get_rework_processes(
        self, product: product.Product, failed_process: process.Process
    ) -> list[process.ReworkProcess]:
        """
        Returns a list of possible rework requests with different resources and processes for the rework process of a product.

        Args:
            product (product.Product): The product to get the rework request for.
            failed_process (process.Process): The failed process.

        Returns:
            list[process.ReworkProcess]: A list of possible rework processes for the product.
        """
        key = (
            product.product_data.product_type,
            failed_process.get_process_signature(),
        )
        return self.rework_compatibility.get(key, [])

    def get_sink(self, _product_type: str) -> sink.Sink:
        """
        Returns the sink for a product type.

        Args:
            _product_type (str): The product type.

        Returns:
            sink.Sink: The sink for the product type.
        """
        possible_sinks = self.sink_factory.get_sinks_with_product_type(_product_type)
        chosen_sink = random.choice(possible_sinks)
        return chosen_sink  # type: ignore False


def FIFO_routing_heuristic(possible_requests: List[request.Request]):
    """
    Sorts the list by the FIFO principle.

    Args:
        possible_resources (List[resources.Resource]): A list of possible resources.
    """
    pass


def random_routing_heuristic(possible_requests: List[request.Request]):
    """
    Shuffles the list of possible resources.

    Args:
        possible_resources (List[resources.Resource]): A list of possible resources.
    """
    possible_requests.sort(key=lambda x: x.resource.data.ID)
    random.shuffle(possible_requests)


def shortest_queue_routing_heuristic(
    possible_requests: List[request.Request],
):
    """
    Sorts the list of possible resources by the length of their input queues and returns the first resource.
    For Transport resources, the next resource is chosen by the resource with the shortest request queue.

    Args:
        possible_resources (List[resources.Resource]): A list of possible resources.
    """
    if any(
        not isinstance(request.resource, resources.ProductionResource)
        for request in possible_requests
    ):
        random.shuffle(possible_requests)
        possible_requests.sort(key=lambda x: len(x.resource.get_controller().requests))
        return
    random.shuffle(possible_requests)
    possible_requests.sort(
        key=lambda x: sum([len(q.items) for q in x.resource.input_queues])
    )


def agent_routing_heuristic(
    gym_env: routing_control_env.AbstractRoutingControlEnv,
    possible_requests: List[request.Request],
):
    """
    Sorts the list of possible resources by an reinforcement learning agent

    Args:
        gym_env (gym_env.ProductionRoutingEnv): Environment for the reinforcement learning agent.
        possible_resources (List[resources.Resource]): A list of possible resources.
    """
    if gym_env.interrupt_simulation_event.triggered:
        # Avoid that multiple requests trigger event multiple times -> delay them
        while possible_requests:
            possible_requests.pop()
        return
    gym_env.set_possible_requests(possible_requests)
    gym_env.interrupt_simulation_event.succeed()


ROUTING_HEURISTIC = {
    "shortest_queue": shortest_queue_routing_heuristic,
    "random": random_routing_heuristic,
    "FIFO": FIFO_routing_heuristic,
}
"""
A dictionary of available routing heuristics.
"""
