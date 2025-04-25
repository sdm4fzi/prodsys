from __future__ import annotations

import random
from typing import (
    List,
    TYPE_CHECKING,
    Callable,
    Generator,
    Optional,
    Union,
    Dict,
    Set,
    Tuple,
)
from dataclasses import dataclass, field

import logging
import time

import simpy

from prodsys.simulation.process_matcher import ProcessMatcher
from prodsys.simulation.request_handler import RequestHandler

logger = logging.getLogger(__name__)

from simpy import events


if TYPE_CHECKING:
    from prodsys.simulation import resources, product, sink, auxiliary, process
    from prodsys.factories import (
        resource_factory,
        sink_factory,
        auxiliary_factory,
        product_factory,
        source_factory,
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
    request_for_transport: Union[request.Request, request.AuxiliaryTransportRequest],
) -> Union[product.Product, auxiliary.Auxiliary]:
    """
    Returns the item to transport from a request.

    Args:
        request_for_transport (Union[request.Request, request.AuxiliaryRequest]): The request.

    Returns:
        Union[product.Product, auxiliary.Auxiliary]: The item to transport.
    """
    if isinstance(request_for_transport, request.AuxiliaryTransportRequest):
        return request_for_transport.auxiliary
    return request_for_transport.product


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
        env: simpy.Environment,
        resource_factory: resource_factory.ResourceFactory,
        sink_factory: sink_factory.SinkFactory,
        auxiliary_factory: auxiliary_factory.AuxiliaryFactory,
        product_factory: Optional[product_factory.ProductFactory] = None,
        source_factory: Optional[source_factory.SourceFactory] = None,
    ):
        self.env = env
        self.resource_factory: resource_factory.ResourceFactory = resource_factory
        self.sink_factory: sink_factory.SinkFactory = sink_factory
        self.auxiliary_factory: auxiliary_factory.AuxiliaryFactory = auxiliary_factory
        self.product_factory: Optional[product_factory.ProductFactory] = product_factory
        self.source_factory: Optional[source_factory.SourceFactory] = source_factory

        self.auxiliary_factory.router = self
        self.product_factory.router = self

        self.reachability_cache: Dict[Tuple[str, str], bool] = {}
        self.route_cache: Dict[Tuple[str, str, str], request.Request] = {}

        self.got_requested = events.Event(self.env)

        # Initialize the resource process mapper with precomputed compatibility tables
        process_matcher = ProcessMatcher(
            self.resource_factory,
            self.sink_factory,
            self.product_factory,
            self.source_factory,
            self.reachability_cache,
            self.route_cache,
        )

        # Initialize the request handler
        self.request_handler = RequestHandler(process_matcher)

        # Initialize compatibility tables

    def mark_finished_request(self, request: request.Request) -> None:
        """
        Marks a resource as free in the router.

        Args:
            resource (resources.Resource): The resource to mark as free.
        """
        if not request.resource.got_free.triggered:
            request.resource.got_free.succeed()
        self.request_handler.mark_completion(request)
        request.completed.succeed()

    def routing_loop(self) -> Generator[None, None, None]:
        """
        Main allocation loop for the router.
        This method should be called in a separate thread to run the allocation process.
        """
        while True:
            yield simpy.AnyOf(
                self.env,
                [self.got_requested]
                + [
                    resource.got_free
                    for resource in self.resource_factory.all_resources
                ],
            )
            if self.got_requested.triggered:
                self.got_requested = events.Event(self.env)
            for resource in self.resource_factory.all_resources:
                if resource.got_free.triggered:
                    resource.got_free = events.Event(self.env)
            while True:
                free_resources = [
                    resource
                    for resource in self.resource_factory.all_resources
                    if not resource.full
                ]
                if not free_resources:
                    break
                free_requests = self.request_handler.get_next_product_to_route(
                    free_resources
                )
                if not free_requests:
                    break
                self.env.update_progress_bar()
                request: request.Request = self.route_request(free_requests)
                self.request_handler.mark_routing(request)
                self.env.process(self.execute_routing(request))

    def execute_routing(
        self, executed_request: request.Request
    ) -> Generator[None, None, None]:
        # reserve input queues
        # reserve transport to resource with a transport request
        if (
            executed_request.request_type != request.RequestType.TRANSPORT
            and executed_request.item.current_locatable != executed_request.target
        ):
            transport_process_finished_event = self.request_transport(executed_request.item, executed_request.resource)
            executed_request.transport_to_target = transport_process_finished_event
            yield transport_process_finished_event
        executed_request.resource.controller.request(executed_request)

    def route_request(self, free_requests: List[request.Request]) -> request.Request:
        """
        Allocates a resource to a request.

        Args:
            free_requests (List[request.Request]): The list of free requests.

        Returns:
            request.Request: The allocated request.
        """
        # Determine based on the routing heuristic
        routing_heuristic = free_requests[0].product.routing_heuristic
        routing_heuristic(free_requests)
        routed_request = free_requests.pop(0)

        # TODO: make queue decision with heuristic here!
        if routed_request.request_type == request.RequestType.TRANSPORT:
            # reserve input queues
            origin_queue = routed_request.origin.output_queues[0]
            target_queue = routed_request.target.input_queues[0]
        elif routed_request.request_type == request.RequestType.PRODUCTION:
            # reserve input queues
            origin_queue = routed_request.resource.input_queues[0]
            target_queue = routed_request.resource.output_queues[0]

        routed_request.origin_queue = origin_queue
        routed_request.target_queue = target_queue
        return routed_request

    def route_auxiliaries_to_product(
        self, product: product.Product
    ) -> Generator[None, None, None]:
        """
        Returns a list of auxiliaries for a product.

        Args:
            product (product.Product): The product.

        Returns:
            List[auxiliary.Auxiliary]: The list of auxiliaries.
        """
        # TODO: this function allocates all required auxiliaries, transports them to the product and locks them
        pass

    def get_auxiliary_for_process(
        self, product: product.Product, process: process.Process
    ) -> Generator[None, None, None]:
        """
        Returns an auxiliary for a process.

        """
        # TODO: this function should select auxiliaries for the process and bring them to the location and lock them
        pass

    def release_auxiliaries_from_process(
        self, product: product.Product, process: process.Process
    ) -> None:
        """
        Releases all auxiliaries from a process.

        Args:
            product (product.Product): The product.
            process (process.Process): The process.
        """
        for auxiliary in process.auxiliaries:
            self.release_auxiliary(auxiliary)

    def release_auxiliaries_from_product(self, product: product.Product) -> None:
        """
        Releases all auxiliaries from a product.

        Args:
            product (product.Product): The product.
        """
        for auxiliary in product.auxiliaries:
            self.release_auxiliary(auxiliary)

    def release_auxiliary(self, auxiliary: auxiliary.Auxiliary) -> None:
        """
        Releases an auxiliary.

        Args:
            auxiliary (auxiliary.Auxiliary): The auxiliary to release.
        """
        auxiliary.got_free.succeed()
        auxiliary.got_free = events.Event(self.env)
        self.request_handler.mark_completion(auxiliary)

    def request_processing(self, product: product.Product) -> events.Event:
        """
        Routes a product to perform the next process by assigning a production resource, that performs the process, to the product
        and assigning a transport resource to transport the product to the next process.

        Args:
            product (product.Product): The product.

        Returns:
            Generator[Tuple[request.Request, request.TransportResquest]]: A generator that yields when the product is routed.
        """
        process_event = self.request_handler.add_product_requests(
            product
        ).request_completion_event
        if not self.got_requested.triggered:
            self.got_requested.succeed()
        return process_event

    def request_transport(self, product: product.Product, target: Locatable) -> events.Event:
        """
        Routes a product to perform the next transport by assigning a transport resource to the product.

        Args:
            product (product.Product): The product.

        Returns:
            Generator[request.TransportResquest]: A generator that yields when the product is routed.
        """
        request_info = self.request_handler.add_transport_request(product, target)
        if not self.got_requested.triggered:
            self.got_requested.succeed()
        return request_info.request_completion_event

    def route_product_to_sink(self, product: product.Product) -> events.Event:
        """
        Routes a product to a sink.

        Args:
            product (product.Product): The product.

        Returns:
            Generator[request.TransportResquest]: A generator that yields when the product is routed to the sink.
        """
        possible_sinks = self.sink_factory.get_sinks_with_product_type(
            product.product_data.product_type
        )
        chosen_sink = random.choice(possible_sinks)
        request_info = self.request_handler.add_transport_request(product, chosen_sink)
        if not self.got_requested.triggered:
            self.got_requested.succeed()
        return request_info.request_completion_event

    def route_product_to_storage(self, product: product.Product):
        """
        Routes a product to the store.

        Args:
            product (product.Product): The product.

        Returns:
            Generator[request.TransportResquest]: A generator that yields when the product is routed to the store.
        """
        # TODO: implement function for working with stores

        # resource = product.current_locatable
        # external_queues = [
        #     queue for queue in resource.output_queues if isinstance(queue, store.Store)
        # ]
        # if not external_queues:
        #     raise ValueError(
        #         f"No external queues found for product {product.product_data.ID} to reach any store from resource {product.current_locatable.data.ID}."
        #     )

        # potential_to_transport_requests = []
        # for external_queue in external_queues:
        #     to_transport_request = request.ToTransportRequest(
        #         product=product, target=external_queue
        #     )
        #     potential_to_transport_requests.append(to_transport_request)

    # def check_store_product(self, product: product.Product) -> bool:
    #     """
    #     Decides whether a product is stored in the store.

    #     Returns:
    #         bool: If the product is stored in the store.
    #     """
    #     resource = product.current_locatable
    #     external_queues = [
    #         queue for queue in resource.output_queues if isinstance(queue, store.Store)
    #     ]
    #     if not external_queues:
    #         return False
    #     internal_queues = [
    #         queue
    #         for queue in resource.output_queues
    #         if not isinstance(queue, store.Store)
    #     ]
    #     if all(queue.full for queue in internal_queues):
    #         return True
    #     # TODO: implement heuristic for storage
    #     return random.choice([True, False])

    def route_resource_to_auxiliary_process(
        resource: resources.Resource, required_process: process.Process
    ) -> Generator[request.AuxiliaryTransportRequest]:
        """
        Routes an auxiliary to a resource.

        Args:
            resource (resources.Resource): The resource.
            required_process (process.Process): The required process.

        Returns:
            Generator: A generator that yields when the auxiliary is routed to the resource.
        """
        # TODO: this function should select a resource than perform the required process

    def bring_resource_to_request_location(
        resource: resources.Resource, request: request.Request
    ) -> Generator[request.TransportResquest]:
        """
        Routes a resource to the location of a request.

        Args:
            resource (resources.Resource): The resource.
            request (request.Request): The request.

        Returns:
            Generator: A generator that yields when the resource is routed to the request location.
        """
        # TODO: either make a move request, if the resource is moveable, otherwise make a transport request

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
        self.request_handler.add_transport_request(auxiliary, auxiliary.storage)

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
    if any(request.resource.can_process for request in possible_requests):
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

from prodsys.simulation import request
