from __future__ import annotations

import random
from typing import (
    List,
    TYPE_CHECKING,
    Generator,
    Optional,
    Union,
    Dict,
    Tuple,
)

import logging

import simpy

from prodsys.factories import primitive_factory
from prodsys.models.dependency_data import DependencyType
from prodsys.models import port_data, production_system_data
from prodsys.simulation.interaction_handler import InteractionHandler
from prodsys.simulation.process_matcher import ProcessMatcher
from prodsys.simulation.request_handler import RequestHandler, RequestInfo

logger = logging.getLogger(__name__)

from simpy import events


if TYPE_CHECKING:
    from prodsys.simulation import resources, product, sink, process, port
    from prodsys.factories import (
        resource_factory,
        sink_factory,
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
    if requests[0].requesting_item:
        return requests[0].requesting_item.env
    else:
        return requests[0].primitive.env


def get_item_to_transport(
    request_for_transport: Union[request.Request, request.AuxiliaryTransportRequest],
) -> Union[product.Product, primitive.Primitive]:
    """
    Returns the item to transport from a request.

    Args:
        request_for_transport (Union[request.Request, request.AuxiliaryRequest]): The request.

    Returns:
        Union[product.Product, auxiliary.Auxiliary]: The item to transport.
    """
    if isinstance(request_for_transport, request.AuxiliaryTransportRequest):
        return request_for_transport.primitive
    return request_for_transport.requesting_item


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
        product_factory: Optional[product_factory.ProductFactory] = None,
        source_factory: Optional[source_factory.SourceFactory] = None,
        primitive_factory: Optional[primitive_factory.PrimitiveFactory] = None,
        production_system_data: Optional[production_system_data.ProductionSystemData] = None,
    ):
        self.env = env
        self.resource_factory: resource_factory.ResourceFactory = resource_factory
        self.sink_factory: sink_factory.SinkFactory = sink_factory
        self.product_factory: Optional[product_factory.ProductFactory] = product_factory
        self.source_factory: Optional[source_factory.SourceFactory] = source_factory
        self.primitive_factory: Optional[primitive_factory.PrimitiveFactory] = (
            primitive_factory
        )
        self.production_system_data: Optional[production_system_data.ProductionSystemData] = production_system_data
        self.free_primitives_by_type: Dict[str, List[primitive.Primitive]] = {}
        for primitive in self.primitive_factory.primitives:
            if primitive.data.type not in self.free_primitives_by_type:
                self.free_primitives_by_type[primitive.data.type] = []
            self.free_primitives_by_type[primitive.data.type].append(primitive)

        self.product_factory.router = self

        self.reachability_cache: Dict[Tuple[str, str], bool] = {}
        self.route_cache: Dict[Tuple[str, str, str], request.Request] = {}

        self.got_requested = events.Event(self.env)
        self.got_primitive_request = events.Event(self.env)
        self.resource_got_free = events.Event(self.env)

        # Initialize the resource process mapper with precomputed compatibility tables
        process_matcher = ProcessMatcher(
            self.resource_factory,
            self.sink_factory,
            self.product_factory,
            self.source_factory,
            self.primitive_factory,
            self.reachability_cache,
            self.route_cache,
        )

        # Initialize the request handler
        self.request_handler = RequestHandler(process_matcher)
        self.interaction_handler = InteractionHandler()

        # Initialize compatibility tables

    def mark_finished_request(self, request: request.Request) -> None:
        """
        Marks a resource as free in the router.

        Args:
            resource (resources.Resource): The resource to mark as free.
        """
        self.request_handler.mark_completion(request)
        request.completed.succeed()
        if not self.resource_got_free.triggered:
            self.resource_got_free.succeed()

    def resource_routing_loop(self) -> Generator[None, None, None]:
        """
        Main allocation loop for the router.
        This method should be called in a separate thread to run the allocation process.
        """
        free_resources = list(self.resource_factory.all_resources.values())
        while True:
            yield self.got_requested
            self.got_requested = events.Event(self.env)
            while True:
                free_requests = self.request_handler.get_next_resource_request_to_route(
                    free_resources
                )
                if not free_requests:
                    break
                self.env.update_progress_bar()
                request: request.Request = self.route_request(free_requests)
                self.request_handler.mark_routing(request)
                self.env.process(self.execute_resource_routing(request))

    def primitive_routing_loop(self) -> Generator[None, None, None]:
        """
        Main allocation loop for the router.
        This method should be called in a separate thread to run the allocation process.
        """
        while True:
            yield self.got_primitive_request
            if not self.free_primitives_by_type:
                continue
            self.got_primitive_request = events.Event(self.env)
            while True:
                free_requests = (
                    self.request_handler.get_next_primitive_request_to_route(
                        self.free_primitives_by_type
                    )
                )
                if not free_requests:
                    break
                self.env.update_progress_bar()
                request: request.Request = self.route_request(free_requests)
                self.request_handler.mark_routing(request)
                self.free_primitives_by_type[request.item.data.type].remove(
                    request.item
                )
                self.env.process(self.execute_primitive_routing(request))

    def execute_resource_routing(
        self, executed_request: request.Request
    ) -> Generator[None, None, None]:
        origin_port, target_port = self.interaction_handler.get_interaction_ports(
            executed_request
        )
        if target_port:
            yield from target_port.reserve()
        if (
            executed_request.request_type == request.RequestType.PRODUCTION
            and executed_request.requesting_item.current_locatable
            != origin_port
        ):
            transport_process_finished_event = self.request_transport(
                executed_request.requesting_item, origin_port
            )
            executed_request.transport_to_target = transport_process_finished_event
            yield transport_process_finished_event

        
        if executed_request.request_type == request.RequestType.TRANSPORT:
            route = self.request_handler.process_matcher.get_route(
                origin_port, target_port, executed_request.process
            )
            executed_request.route = route

        executed_request.origin_queue = origin_port
        executed_request.target_queue = target_port

        executed_request.resource.controller.request(executed_request)
        if executed_request.required_dependencies:
            yield executed_request.dependencies_requested
            dependency_ready_events = self.get_dependencies_for_execution(
                resource=executed_request.resource,
                process=executed_request.process,
                requesting_item=executed_request.requesting_item,
                dependency_release_event=executed_request.completed,
            )
            for dependency_ready_event in dependency_ready_events:
                yield dependency_ready_event
            executed_request.dependencies_ready.succeed()
            yield executed_request.completed

    def request_buffering(self, executed_request: request.Request) -> Optional[events.Event]:
        buffer = self.interaction_handler.get_interaction_buffer(executed_request)
        if not buffer:
            return None
        transport_process_finished_event = self.request_transport(
            executed_request.requesting_item, buffer
        )
        executed_request.transport_to_target = transport_process_finished_event
        return transport_process_finished_event

    def execute_primitive_routing(
        self, executed_request: request.Request
    ) -> Generator[None, None, None]:
        executed_request.item.bind(
            executed_request.requesting_item, executed_request.resolved_dependency
        )

        # TODO: add here with interaction handler searching for interaction points
        trans_process_finished_event = self.request_transport(
            executed_request.item, executed_request.requesting_item.current_locatable
        )
        yield trans_process_finished_event
        # retrieve item here from queue and make sure its position is updated!
        executed_request.completed.succeed()
        if (
            executed_request.dependency_release_event
        ):  # primitives for resource processes
            yield executed_request.dependency_release_event
        else:  # primitives for product
            yield executed_request.item.got_free
        # Find an appropriate storage for the primitive
        target_storage = self._find_available_storage_for_primitive(executed_request.item)
        transport_process_finished_event = self.request_transport(
            executed_request.item, target_storage
        )
        yield transport_process_finished_event
        self.free_primitives_by_type[executed_request.item.data.type].append(
            executed_request.item
        )
        if not self.got_primitive_request.triggered:
            self.got_primitive_request.succeed()

    def _find_available_storage_for_primitive(self, primitive: primitive.Primitive) -> port.Store:
        """
        Find an available storage for a primitive. For primitives with multiple storages,
        this method finds the first available storage that can accept the primitive.
        
        Args:
            primitive (primitive.Primitive): The primitive to find storage for.
            
        Returns:
            port.Store: An available storage for the primitive.
        """
        # TODO: this logic should be moved to the interaction handler!
        # Get the primitive data to find all possible storages
        primitive_data = None
        # Find the original primitive data that defines the storages
        if self.production_system_data:
            for orig_p_data in self.production_system_data.primitive_data:
                if orig_p_data.type == primitive.data.type:
                    primitive_data = orig_p_data
                    break
        
        if not primitive_data or not hasattr(primitive_data, 'storages'):
            # Fallback to the primitive's home storage if we can't find the data
            return primitive.storage
        
        # Get all possible storages for this primitive type
        possible_storages = []
        for storage_id in primitive_data.storages:
            storage = self.primitive_factory.queue_factory.get_queue(storage_id)
            if hasattr(storage, 'data') and storage.data.port_type == port_data.PortType.STORE:
                possible_storages.append(storage)
        
        if not possible_storages:
            # Fallback to the primitive's home storage
            return primitive.storage
        
        # Try to find a storage with available capacity
        for storage in possible_storages:
            if storage._is_full():
                continue
            return storage
        
        # If no storage has capacity, try to find the one with most space
        if possible_storages:
            best_storage = min(possible_storages, key=lambda s: len(s.items) if hasattr(s, 'items') else 0)
            return best_storage
        
        # Fallback to the first storage if none found
        return possible_storages[0] if possible_storages else primitive.storage

    def route_request(self, free_requests: List[request.Request]) -> request.Request:
        """
        Allocates a resource to a request.

        Args:
            free_requests (List[request.Request]): The list of free requests.

        Returns:
            request.Request: The allocated request.
        """
        try:
            routing_heuristic = free_requests[0].requesting_item.routing_heuristic
            routing_heuristic(free_requests)
        except Exception:
            routing_heuristic = lambda x: x[0]
            routing_heuristic(free_requests)
        routed_request = free_requests.pop(0)

        # origin_queue, target_queue = self.interaction_handler.get_interaction_ports(
        #     routed_request
        # )
        # if routed_request.request_type == request.RequestType.TRANSPORT:
        #     route = self.request_handler.process_matcher.get_route(
        #         origin_queue, target_queue, routed_request.process
        #     )
        #     routed_request.route = route

        # routed_request.origin_queue = origin_queue
        # routed_request.target_queue = target_queue
        return routed_request

    def get_dependencies_for_product_processing(
        self, product: product.Product
    ) -> List[RequestInfo]:
        """
        Routes all dependencies for processing to a product. Covers currently only primitive dependencies (workpiece carriers, e.g.)

        Args:
            product (product.Product): The product.

        Returns:
            Generator[None, None, None]: A generator that yields when the dependencies are routed.
        """
        request_infos = []
        for dependency in product.dependencies:
            assert (
                dependency.data.dependency_type == DependencyType.PRIMITIVE
            ), f"Only primitive dependencies are supported for now. Found {dependency.data.dependency_type} for {product.data.ID}."
            request_info = self.request_handler.add_dependency_request(
                requiring_dependency=product,
                dependency=dependency,
                requesting_item=product,
            )
            request_infos.append(request_info)
        if not self.got_primitive_request.triggered:
            self.got_primitive_request.succeed()
        return request_infos

    def get_dependencies_for_execution(
        self,
        resource: resources.Resource,
        process: process.Process,
        requesting_item: Union[product.Product, primitive.Primitive],
        dependency_release_event: events.Event,
    ) -> List[simpy.Event]:
        """
        Routes all dependencies for processing to a resource. Covers currently only primitive dependencies (workpiece carriers, e.g.)
        Args:
            resource (resources.Resource): The resource.
        Returns:
            Generator[None, None, None]: A generator that yields when the dependencies are routed.
        """
        # could be primitives, processes or resources
        # for primitives, same logic as for products
        # for processes, find a suiting resource and route it to the resource
        # for resources, find resource and route it to this resource

        # only one object can be immovable, the other has to be movable -> go always to the immovable one
        dependency_ready_events = []
        for dependency in resource.dependencies:
            request_info = self.request_handler.add_dependency_request(
                requiring_dependency=resource,
                requesting_item=requesting_item,
                dependency=dependency,
                dependency_release_event=dependency_release_event,
            )
            dependency_ready_events.append(request_info.request_completion_event)
        for dependency in process.dependencies:
            request_info = self.request_handler.add_dependency_request(
                requiring_dependency=resource,
                dependency=dependency,
                requesting_item=requesting_item,
            )
            dependency_ready_events.append(request_info.request_completion_event)
        return dependency_ready_events

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

    def request_transport(
        self, product: product.Product, target: Locatable
    ) -> events.Event:
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

    def route_product_to_sink(self, product: product.Product) -> tuple[events.Event, sink.Sink]:
        """
        Routes a product to a sink.

        Args:
            product (product.Product): The product.

        Returns:
            Generator[request.TransportResquest]: A generator that yields when the product is routed to the sink.
        """
        possible_sinks = self.sink_factory.get_sinks_with_product_type(
            product.data.type
        )
        chosen_sink = random.choice(possible_sinks)
        # TODO: move retrieving chosen sink ports to interactin handler!
        target_port = chosen_sink.ports[0]
        request_info = self.request_handler.add_transport_request(product, target_port)
        if not self.got_requested.triggered:
            self.got_requested.succeed()
        return request_info.request_completion_event, chosen_sink

    def get_rework_processes(
        self, failed_process: process.Process
    ) -> list[process.ReworkProcess]:
        """
        Returns a list of possible rework requests with different resources and processes for the rework process of a product.

        Args:
            product (product.Product): The product to get the rework request for.
            failed_process (process.Process): The failed process.

        Returns:
            list[process.ReworkProcess]: A list of possible rework processes for the product.
        """
        return self.request_handler.get_rework_processes(failed_process=failed_process)


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
    possible_requests.sort(key=lambda x: sum([len(q.items) for q in x.resource.ports]))


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

from prodsys.simulation import primitive, request
