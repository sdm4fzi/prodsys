from __future__ import annotations

from collections.abc import Callable
from typing import List, TYPE_CHECKING, Generator, Optional, Union

import logging

import simpy
logger = logging.getLogger(__name__)

import numpy as np

from simpy import events

from prodsys.simulation import resources
from prodsys.simulation import request
from prodsys.simulation.process import ReworkProcess


if TYPE_CHECKING:
    from prodsys.simulation import resources, product, sink, auxiliary, process, store
    from prodsys.factories import resource_factory, sink_factory, auxiliary_factory, product_factory
    from prodsys.control import routing_control_env
    from prodsys.models import product_data
    from prodsys.simulation.product import Locatable


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


def get_item_to_transport(request_for_transport: Union[request.Request, request.AuxiliaryRequest]) -> Union[product.Product, auxiliary.Auxiliary]:
    """
    Returns the item to transport from a request.

    Args:
        request_for_transport (Union[request.Request, request.AuxiliaryRequest]): The request.

    Returns:
        Union[product.Product, auxiliary.Auxiliary]: The item to transport.
    """
    if isinstance(request_for_transport, request.AuxiliaryRequest):
        return request_for_transport.auxiliary
    return  request_for_transport.product


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
        product_factory: product_factory.ProductFactory,
        resource_factory: resource_factory.ResourceFactory,
        sink_factory: sink_factory.SinkFactory,
        auxiliary_factory: auxiliary_factory.AuxiliaryFactory,
        routing_heuristic: Callable[[List[request.Request]], None],
    ):
        self.product_factory: product_factory.ProductFactory = product_factory
        self.resource_factory: resource_factory.ResourceFactory = resource_factory
        self.sink_factory: sink_factory.SinkFactory = sink_factory
        self.auxiliary_factory: auxiliary_factory.AuxiliaryFactory = auxiliary_factory
        self.routing_heuristic: Callable[[List[request.Request]], None] = routing_heuristic
        self._is_routing_to_warehouse = None
        # TODO: add possibility to specify a production and a transport heuristic separately
    
    def route_product_to_production_resource(self, product: product.Product) -> Generator[Optional[request.Request]]:
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
            raise ValueError(f"No possible production resources found for product {product.product_data.ID} and process {product.next_prodution_process.process_data.ID}.")
        potential_transport_requests: List[request.Request] = []

        potential_transport_requests = self.get_possible_transport_requests(potential_production_requests)
        if not potential_transport_requests:
            raise ValueError(f"No possible transport resources found for product {product.product_data.ID} and process {product.next_prodution_process.process_data.ID} to reach any destinations from resource {product.current_locatable.data.ID}.")
        possible_production_requests = self.get_reachable_production_requests(potential_production_requests, potential_transport_requests)
    
        env = get_env_from_requests(potential_transport_requests)
        routed_production_request = yield env.process(self.get_routed_production_request(possible_production_requests))
        return routed_production_request
    

    def get_input_queue_state_change_events(self, possible_requests: List[request.Request]) -> List[events.Event]:
        """
        Returns the state change events of the input queues of the resources of the requests.

        Args:
            possible_requests (List[request.Request]): The requests.

        Returns:
            List[events.Event]: The state change events of the input queues of the resources of the requests.
        """
        possible_resources: List[resources.ProductionResource] = []
        for request in possible_requests:
            if not request.resource in possible_resources and isinstance(request.resource, resources.ProductionResource):
                possible_resources.append(request.resource)
        input_queue_get_events = []
        for resource in possible_resources:
            for queue in resource.input_queues:
                input_queue_get_events.append(queue.state_change)
        return input_queue_get_events
    

    def get_routed_production_request(self, possible_production_requests: List[request.Request]) -> Generator[Optional[request.Request]]:
        env = get_env_from_requests(possible_production_requests)
        while True:
            production_requests: List[request.Request] = self.get_requests_with_non_blocked_resources(possible_production_requests)
            if production_requests:
                break
            logger.debug({"ID": possible_production_requests[0].product.product_data.ID, "sim_time": env.now, "event": f"Waiting for free resources."})
            yield events.AnyOf(
                env,
                self.get_input_queue_state_change_events(possible_production_requests),
            )
            logger.debug({"ID": possible_production_requests[0].product.product_data.ID, "sim_time": env.now, "event": f"Free resources available."})

        self.routing_heuristic(production_requests)
        if not production_requests:
            return
        routed_production_request = production_requests.pop(0)
        #TODO: change logic with reservation of queues -> do not reserve all input queues but make routing to queue here
        routed_production_request.resource.reserve_input_queues()
        return routed_production_request

    def route_transport_resource_for_item(self, item_to_transport, resource) -> Generator[Optional[request.TransportResquest]]:
    #TODO: check merge
    #def route_transport_resource_for_product(self, product: product.Product, resource: resources.ProductionResource) -> Generator[Optional[request.TransportResquest]]:
        """
        Routes a product to perform the next process by assigning a production resource, that performs the process, to the product 
        and assigning a transport resource to transport the product to the next process.

        Args:
            item_to_transport (Union[product.Product, auxiliary.Auxiliary]): The product or auxiliary to transport.
            routed_production_request (Union[request.Request, request.AuxiliaryRequest]): The production request or auxiliary request.

        Returns:
            Generator[Optional[request.TransportResquest]]: A generator that yields when the product is routed.
        """
        #item_to_transport = get_item_to_transport(routed_production_request)
        potential_transport_requests: List[request.Request] = self.get_transport_requests_to_target(item_to_transport, resource, {})

        if not potential_transport_requests:
            raise ValueError(f"No possible transport resources found for product {item_to_transport.product_data.ID} and process {item_to_transport.next_prodution_process.process_data.ID} to reach any destinations from resource {item_to_transport.current_locatable.data.ID}.")
        
        env = get_env_from_requests(potential_transport_requests)
        while True:
            transport_requests: List[request.TransportResquest] = self.get_requests_with_non_blocked_resources(potential_transport_requests)
            if transport_requests:
                break
            logger.debug({"ID": item_to_transport.product_data.ID, "sim_time": env.now, "event": f"Waiting for free resources."})
            yield events.AnyOf(
                env,
                self.get_input_queue_state_change_events(potential_transport_requests),
            )
            logger.debug({"ID": item_to_transport.product_data.ID, "sim_time": env.now, "event": f"Free resources available."})
        if not transport_requests:
            raise ValueError(f"No transport requests found for routing of product {item_to_transport.product_data.ID}. Error in Event handling of routing to resources.")
        self.routing_heuristic(transport_requests)
        yield env.timeout(0)
        if not transport_requests:
            return
        routed_transport_request = transport_requests.pop(0)
        return routed_transport_request
    

    def route_product_to_sink(self, product: product.Product) -> Generator[Optional[request.TransportResquest]]:
        """
        Routes a product to a sink.

        Args:
            product (product.Product): The product.

        Returns:
            Generator[request.TransportResquest]: A generator that yields when the product is routed to the sink.
        """
        sink = self.get_sink(product.product_data.product_type)
        sink_request = request.SinkRequest(product=product, sink=sink)
        potential_transport_requests = self.get_possible_transport_requests([sink_request])
        if not potential_transport_requests:
            raise ValueError(f"No possible transport resources found for product {product.product_data.ID} to reach any sinks from resource {product.current_locatable.data.ID}.")
        env = get_env_from_requests(potential_transport_requests)
        while True:
            transport_requests: List[request.TransportResquest] = self.get_requests_with_non_blocked_resources(potential_transport_requests)
            if transport_requests:
                break
            logger.debug({"ID": product.product_data.ID, "sim_time": env.now, "event": f"Waiting for free resources."})
            yield events.AnyOf(
                env,
                self.get_input_queue_state_change_events(potential_transport_requests),
            )
            logger.debug({"ID": product.product_data.ID, "sim_time": env.now, "event": f"Free resources available."})
        if not transport_requests:
            raise ValueError(f"No transport requests found for routing of product {product.product_data.ID}. Error in Event handling of routing to resources.")
        self.routing_heuristic(transport_requests)
        yield env.timeout(0)
        if not transport_requests:
            return
        routed_transport_request = transport_requests.pop(0)
        return routed_transport_request
    
    def route_product_to_warehouse(self, product: product.Product) -> Generator[request.TransportResquest]:
        """
        Routes a product to the warehouse.

        Args:
            product (product.Product): The product.

        Returns:
            Generator[request.TransportResquest]: A generator that yields when the product is routed to the warehouse.
        """
        resource = product.current_locatable
        external_queues = [queue for queue in resource.output_queues if queue.input_location]

        chosen_warehouse = np.random.choice(external_queues)
        env = product.env
        transport_request = yield env.process(self.route_transport_resource_for_item(product, chosen_warehouse))
        
        chosen_warehouse.reserve()
        
        return transport_request

    def route_product_from_warehouse(self, product: product.Product, resource: resources.ProductionResource) -> Generator[request.TransportResquest]:
        """
        Routes a product from the warehouse.

        Args:
            product (product.Product): The product.

        Returns:
            Generator[request.TransportResquest]: A generator that yields when the product is routed from the warehouse.
        """
        env = product.env
        transport_request = yield env.process(self.route_transport_resource_for_item(product, resource))
        return transport_request
    
    def check_store_product_in_warehouse(product: product.Product) -> bool:
        """
        Decides whether a product is stored in the warehouse.

        Returns:
            bool: If the product is stored in the warehouse.
        """
        resource = product.current_locatable
        external_queues = [queue for queue in resource.output_queues if queue.input_location]
        if not external_queues:
            return False
        #TODO: implement heuristic
        return np.random.choice([True, False])

    def get_requests_with_free_resources(self, potential_requests: List[request.Request]) -> Generator[List[request.Request]]:
        """
        Returns a list of requests with free resources.

        Args:
            potential_requests (List[request.Request]): A list of potential requests.

        Returns:
            Generator[List[request.Request]]: A generator that yields when the requests are routed.
        """
        while True:
            free_resources = self.get_requests_with_non_blocked_resources(potential_requests)
            env = get_env_from_requests(potential_requests)
            yield env.timeout(0)
            if free_resources:
                return free_resources
            logger.debug({"ID": potential_requests[0].product.product_data.ID, "sim_time": env.now, "event": f"Waiting for free resources."})
            yield events.AnyOf(
                [resource.got_free for resource in self.resource_factory.resources],
            )
            logger.debug({"ID": potential_requests[0].product.product_data.ID, "sim_time": env.now, "event": f"Free resources available."})

    def get_production_request(self, product: product.Product, resource: resources.Resource) -> request.Request:
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
    
    def get_transport_request(self, item_to_transport: Union[product.Product, auxiliary.Auxiliary], transport_resource: resources.TransportResource, target: resources.Resource) -> request.TransportResquest:
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
    

    def route_auxiliary_to_product(self, product: product.Product) -> Generator[request.AuxiliaryRequest]:
        """
        Routes an auxiliary to a product.

        Args:
            product (product.Product): The product.

        Returns:
            Generator: A generator that yields when the auxiliary is routed to the product.
        """
        auxiliary_request = request.AuxiliaryRequest(product=product, process=product.transport_process)
        yield product.env.process(self.get_auxiliary(auxiliary_request))
        yield product.env.timeout(0)
        return auxiliary_request
    
    def route_auxiliary_to_store(self, auxiliary: auxiliary.Auxiliary) -> Generator[request.TransportResquest]:
        """
        Routes an auxiliary to a store.

        Args:
            auxiliary (auxiliary.Auxiliary): The auxiliary.

        Returns:
            Generator: A generator that yields when the auxiliary is routed to the store.
        """
        auxiliary_request = request.AuxiliaryRequest(auxiliary=auxiliary, process=auxiliary.transport_process, resource=auxiliary.storage, product=None)
        # transport_request = self.get_transport_request(auxiliary, auxiliary.transport_process, auxiliary.storage)
        env = get_env_from_requests([auxiliary_request])
        transport_request: request.TransportResquest = yield env.process(self.route_transport_resource_for_item(auxiliary_request.auxiliary, auxiliary_request.resource))
        yield env.timeout(0)
        return transport_request


    def get_auxiliary(self, processing_request: request.AuxiliaryRequest) -> Generator:

        possible_auxiliaries = self.get_possible_auxiliaries(processing_request)
        while True:
            free_possible_auxiliaries = self.get_free_auxiliary(possible_auxiliaries)
            # TODO: maybe make heuristic working for selecting auxiliary...
            np.random.shuffle(free_possible_auxiliaries)
            if free_possible_auxiliaries:
                break
            logger.info({"ID": processing_request.product.product_data.ID , "sim_time": processing_request.product.env.now, "event": f"Waiting for free auxiliary."})
            yield events.AnyOf(
                processing_request.product.env,
                [auxiliary.got_free for auxiliary in possible_auxiliaries],
            )
            logger.info({"ID": processing_request.product.product_data.ID, "sim_time": processing_request.product.env.now, "event": f"Free auxiliary available."})
        routed_auxiliary = free_possible_auxiliaries[0]
        routed_auxiliary.reserve()
        routed_auxiliary.got_free = events.Event(processing_request.product.env)
        routed_auxiliary.current_product = processing_request.product
        processing_request.auxiliary = routed_auxiliary
        processing_request.resource = processing_request.product.current_locatable

    def get_free_auxiliary(self, possible_auxiliaries: List[auxiliary.Auxiliary]) -> List[auxiliary.Auxiliary]:

        free_possible_auxiliaries = []
        for auxiliary in possible_auxiliaries:
            if not auxiliary.reserved and auxiliary.current_product is None:
                free_possible_auxiliaries.append(auxiliary)
        return free_possible_auxiliaries
    
    def get_possible_auxiliaries(self, processing_request: request.AuxiliaryRequest)-> List[auxiliary.Auxiliary]:
        possible_auxiliaries = []
        for auxiliary in self.auxiliary_factory.auxiliaries:
            if not auxiliary.data.auxiliary_type in processing_request.product.product_data.auxiliaries:
                continue
            if any(supported_process.matches_request(processing_request) for supported_process in auxiliary.relevant_processes + auxiliary.relevant_transport_processes):
                possible_auxiliaries.append(auxiliary)
        return possible_auxiliaries
    
    def get_possible_production_requests(self, product: product.Product) -> List[request.Request]:
        """
        Returns a list of possible production requests with different resources and processes for the next production process of a product.

        Args:
            product (product.Product): The product to get the request for.

        Returns:
            List[request.Request]: A list of possible production requests for the next production process of the product.
        """
        possible_requests = []
        for resource in self.resource_factory.get_production_resources():
            for process in resource.processes:
                production_request = self.get_production_request(product, resource)
                if process.matches_request(production_request):
                    production_request.set_process(process)
                    possible_requests.append(production_request)
        return possible_requests
    
    def get_reachable_production_requests(self, production_requests: List[request.Request], transport_requests: List[request.TransportResquest]) -> List[request.Request]:
        """
        Returns a list of production requests that are reachable by the transport requests.

        Args:
            production_requests (List[request.Request]): potential production requests
            transport_requests (List[request.Request]): potential transport requests

        Returns:
            List[request.Request]: A list of production requests that are reachable by the transport requests.
        """
        possible_production_resource_ids = set([request.target.data.ID for request in transport_requests])
        return [request for request in production_requests if request.resource.data.ID in possible_production_resource_ids]
    
    def get_possible_transport_requests(self, production_requests: List[request.Request]) -> List[request.TransportResquest]:
        """
        Returns a list of possible transport requests with different resources and processes for the next transport process of a product.

        Args:
            production_request (request.Request): The production request to get the transport request for.

        Returns:
            List[request.TransportResquest]: A list of possible transport requests for the next transport process of the product.
        """
        if self._is_routing_to_warehouse:
            transport_target_ids = set([request.resource.data.ID for request in production_requests])
            transport_targets = [resource for resource in self.resource_factory.queue_factory.queues if resource.data.ID in transport_target_ids]
        elif any(isinstance(production_request, request.SinkRequest) for production_request in production_requests):
            transport_targets = [request.resource for request in production_requests]
        else:
            transport_target_ids = set([request.resource.data.ID for request in production_requests])
            transport_targets = [resource for resource in self.resource_factory.resources if resource.data.ID in transport_target_ids]
        product = production_requests[0].product

        possible_requests = []
        route_cache = {}

        for transport_target in transport_targets:
            possible_requests += self.get_transport_requests_to_target(product, transport_target, route_cache)

        for resource in self.resource_factory.get_transport_resources():
            for process in resource.processes:
                for target in transport_targets:
                    transport_request = self.get_transport_request(product, resource, target)
                    if hasattr(target, 'queue_data'):
                        target_id = target.data.ID
                    else:
                        target_id = target.data.ID
                    if route_cache.get((target_id, process.process_data.ID)):
                        transport_request.copy_cached_routes(route_cache[(target_id, process.process_data.ID)])
                        transport_request.set_process(process)
                        possible_requests.append(transport_request)
                    elif process.matches_request(transport_request):
                        possible_requests.append(transport_request)
                        transport_request.set_process(process)
                        route_cache[(target_id, process.process_data.ID)] = transport_request
        return possible_requests
    


    def get_transport_requests_to_target(self, item_to_transport: Union[product.Product, auxiliary.Auxiliary], target: Locatable, route_cache: dict) -> List[request.TransportResquest]:
        """
        Returns a list of transport requests with different resources and processes for the next transport process of a product.

        Args:
            transport_target (resources.Resource): The transport target to get the transport requests for.

        Returns:
            List[request.TransportResquest]: A list of transport requests for the transport target.
        """
        transport_requests = []
        for resource in self.resource_factory.get_transport_resources():
            for process in resource.processes:
                transport_request = self.get_transport_request(item_to_transport, resource, target)
                if route_cache.get((target.data.ID, process.process_data.ID)):
                    transport_request.copy_cached_routes(route_cache[(target.data.ID, process.process_data.ID)])
                    transport_request.set_process(process)
                    transport_requests.append(transport_request)
                elif process.matches_request(transport_request):
                    transport_request.set_process(process)
                    transport_requests.append(transport_request)
                    route_cache[(target.data.ID, process.process_data.ID)] = transport_request
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
            env = get_env_from_requests([request])
        return [request for request in requests if isinstance(request.resource, resources.TransportResource) or (isinstance(request.resource, resources.ProductionResource) and not any(q.full for q in request.resource.input_queues))]
    
    def get_rework_processes(self, product: product.Product, failed_process: process.Process) -> process.Process:
        """
        Returns a list of possible rework requests with different resources and processes for the rework process of a product.

        Args:
            product (product.Product): The product to get the rework request for.

        Returns:
            List[request.Request]: A list of possible rework requests for the rework process of the product.
        """

        for potential_rework_process in self.resource_factory.process_factory.processes:
            if isinstance(potential_rework_process, ReworkProcess):
                rework_request = request.Request(
                    process=failed_process,
                    product=product,
                    resource=None,
                )
                if potential_rework_process.matches_request(rework_request):
                    return [potential_rework_process]
        return None

    def get_sink(self, _product_type: str) -> sink.Sink:
        """
        Returns the sink for a product type.

        Args:
            _product_type (str): The product type.

        Returns:
            sink.Sink: The sink for the product type.
        """
        possible_sinks = self.sink_factory.get_sinks_with_product_type(_product_type)
        chosen_sink = np.random.choice(possible_sinks)
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
    np.random.shuffle(possible_requests)


def shortest_queue_routing_heuristic(
    possible_requests: List[request.Request],
):
    """
    Sorts the list of possible resources by the length of their input queues and returns the first resource.
    For Transport resources, the next resource is chosen by the resource with the shortest request queue.

    Args:
        possible_resources (List[resources.Resource]): A list of possible resources.
    """
    if any(not isinstance(request.resource, resources.ProductionResource) for request in possible_requests):
        np.random.shuffle(possible_requests)
        possible_requests.sort(key=lambda x: len(x.resource.get_controller().requests))
        return
    np.random.shuffle(possible_requests)
    possible_requests.sort(key=lambda x: sum([len(q.items) for q in x.resource.input_queues]))


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