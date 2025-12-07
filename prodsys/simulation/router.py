from __future__ import annotations

import random
from typing import (
    List,
    TYPE_CHECKING,
    Generator,
    Optional,
    Union,
    Dict,
)

import logging

import simpy

from prodsys.factories import primitive_factory
from prodsys.models.dependency_data import DependencyType
from prodsys.simulation.dependency import Dependency
from prodsys.models import port_data, production_system_data
from prodsys.simulation.interaction_handler import InteractionHandler
from prodsys.simulation.process_matcher import ProcessMatcher
from prodsys.simulation.request_handler import RequestHandler
from prodsys.simulation.entities.entity import EntityType


from simpy import events


if TYPE_CHECKING:
    from prodsys.simulation import resources, sink, process, port
    from prodsys.factories import (
        resource_factory,
        sink_factory,
        product_factory,
        source_factory,
    )
    from prodsys.simulation.entities import product
    
    from prodsys.control import routing_control_env
    from prodsys.simulation.locatable import Locatable

    # from prodsys.factories.source_factory import SourceFactory


logger = logging.getLogger(__name__)

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
        resources: Optional[List[resources.Resource]] = None,
        process_matcher: Optional[ProcessMatcher] = None,
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
        for prim in self.primitive_factory.primitives:
            if prim.data.type not in self.free_primitives_by_type:
                self.free_primitives_by_type[prim.data.type] = []
            self.free_primitives_by_type[prim.data.type].append(prim)

        self.resources = resources
        self.process_matcher: ProcessMatcher = process_matcher

        self.free_resources: Dict[str, resources.Resource] = {resource.data.ID: resource for resource in self.resources}

        self.got_requested = events.Event(self.env)
        self.got_primitive_request = events.Event(self.env)
        self.resource_got_free = events.Event(self.env)

        # Initialize the request handler
        self.request_handler = RequestHandler(self.process_matcher)
        self.interaction_handler = InteractionHandler()

        # Initialize compatibility tables

    def mark_finished_request(self, request: request.Request) -> None:
        """
        Marks a resource as free in the router.

        Args:
            resource (resources.Resource): The resource to mark as free.
        """
        self.request_handler.mark_completion(request)
        if request.entity.type == EntityType.LOT:
            for completed_event in request.entity.all_completed_events:
                completed_event.succeed()
        else:
            request.completed.succeed()
        if not self.resource_got_free.triggered:
            self.resource_got_free.succeed()

    def mark_resource_free(self, resource: resources.Resource) -> None:
        """
        Marks a resource as free in the router.
        """
        if resource.data.ID not in self.free_resources:
            self.free_resources[resource.data.ID] = resource

    def mark_resource_not_free(self, resource: resources.Resource) -> None:
        """
        Marks a resource as not free in the router.
        """
        if resource.data.ID in self.free_resources:
            self.free_resources.pop(resource.data.ID)

    def update_free_resources(self) -> None:
        """
        Updates the list of free resources.
        For INPUT_OUTPUT queues, we need special handling: a resource should be considered
        free if it has items in INPUT_OUTPUT queues that can be processed (removed and put back).
        """
        for resource in self.resources:
            if resource.full:
                self.mark_resource_not_free(resource)
            else:
                # Check OUTPUT and INPUT_OUTPUT ports
                output_ports = [port for port in resource.ports if port.data.interface_type in [port_data.PortInterfaceType.OUTPUT, port_data.PortInterfaceType.INPUT_OUTPUT]]
                if output_ports:
                    # For INPUT_OUTPUT queues: if there are items in the queue, the resource can still process them
                    # even if the queue appears full (because items will be removed then put back)
                    all_ports_full_with_no_items = True
                    for port in output_ports:
                        if port.data.interface_type == port_data.PortInterfaceType.INPUT_OUTPUT:
                            # INPUT_OUTPUT queue: if it has items, resource can process (items will be removed)
                            if len(port.items) > 0:
                                all_ports_full_with_no_items = False
                                break
                        # For OUTPUT or full INPUT_OUTPUT with no items: check if full
                        if not port.is_full:
                            all_ports_full_with_no_items = False
                            break
                    
                    if all_ports_full_with_no_items:
                        self.mark_resource_not_free(resource)
                    else:
                        self.mark_resource_free(resource)
                else:
                    # No output ports, just check if resource is full
                    self.mark_resource_free(resource)

    def resource_routing_loop(self) -> Generator[None, None, None]:
        """
        Main allocation loop for the router.
        This method should be called in a separate thread to run the allocation process.
        """
        while True:
            # Wait for either new requests or resources becoming free
            yield simpy.AnyOf(self.env, [self.got_requested, self.resource_got_free])
            # Reset events if they were triggered
            if self.got_requested.triggered:
                self.got_requested = events.Event(self.env)
            if self.resource_got_free.triggered:
                self.resource_got_free = events.Event(self.env)
            while True:
                self.update_free_resources()
                free_requests = self.request_handler.get_next_resource_request_to_route(
                    list(self.free_resources.values())
                )
                if not free_requests:
                    break
                self.env.update_progress_bar()
                # Filter out requests that would cause deadlocks by checking target queue availability
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
            self.got_primitive_request = events.Event(self.env)
            has_free_primitives = any(
                primitives for primitives in self.free_primitives_by_type.values()
            )
            if not has_free_primitives:
                # If no free primitives but there are pending requests, 
                # we still need to wait for primitives to be released
                # The event will be triggered in execute_primitive_routing when primitives are released
                continue        
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
                self.free_primitives_by_type[request.entity.data.type].remove(
                    request.entity
                )
                self.env.process(self.execute_entity_routing(request))

    def execute_resource_routing(
        self, executed_request: request.Request
    ) -> Generator[None, None, None]:
        origin_port, target_port = self.interaction_handler.get_interaction_ports(
            executed_request
        )
        is_production_request = executed_request.request_type in (
            request.RequestType.PRODUCTION,
            request.RequestType.PROCESS_MODEL,
        )

        if (
            is_production_request
            and executed_request.requesting_item._current_locatable
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
            executed_request.set_route(route=route)

        executed_request.origin_queue = origin_port
        executed_request.target_queue = target_port

        # Don't reserve target port here for production requests - it will be reserved in the production handler
        # after getting items from the origin queue. This prevents premature queue slot locking.
        # Target reservation happens in production_process_handler.py after get_entities_of_request()

        executed_request.resource.controller.request(executed_request)
        # Check for resource and process dependencies - they might not be in required_dependencies
        # if they were set on the resource/process but not passed through required_dependencies
        resource_dependencies = [d for d in executed_request.resource.dependencies if d.data.dependency_type == DependencyType.RESOURCE or d.data.dependency_type == DependencyType.PROCESS]
        process_dependencies = [d for d in executed_request.process.dependencies if d.data.dependency_type == DependencyType.PROCESS]
        all_dependencies = (executed_request.required_dependencies or []) + resource_dependencies + process_dependencies
        
        if all_dependencies:
            # Ensure dependencies_requested event exists
            if not executed_request.dependencies_requested:
                executed_request.dependencies_requested = simpy.Event(executed_request.requesting_item.env)
            yield executed_request.dependencies_requested
            yield from self.get_dependencies(executed_request)
            if not executed_request.dependencies_ready:
                executed_request.dependencies_ready = simpy.Event(executed_request.requesting_item.env)
            executed_request.dependencies_ready.succeed()

    def get_dependencies(self, executed_request: request.Request) -> Generator:        
        entity_dependencies = [dependency for dependency in executed_request.required_dependencies if dependency.data.dependency_type == DependencyType.TOOL or dependency.data.dependency_type == DependencyType.ASSEMBLY]
        # Resource dependencies can be either RESOURCE or PROCESS type (process dependencies can be on the resource)
        resource_dependencies = [dependency for dependency in executed_request.resource.dependencies if dependency.data.dependency_type == DependencyType.RESOURCE or dependency.data.dependency_type == DependencyType.PROCESS]
        process_dependencies = [dependency for dependency in executed_request.process.dependencies if dependency.data.dependency_type == DependencyType.PROCESS]
        
        # For per_lot dependencies with a lot entity, use the lot as the requesting_item
        # Otherwise use the original requesting_item
        requesting_item_for_dependencies = executed_request.requesting_item
        if executed_request.entity.type == EntityType.LOT:
            requesting_item_for_dependencies = executed_request.entity
        
        dependency_ready_events = self.get_dependencies_for_execution(
            resource=executed_request.resource,
            relevant_dependencies=entity_dependencies,
            requesting_item=requesting_item_for_dependencies,
            dependency_release_event=executed_request.completed,
            parent_origin_queue=executed_request.origin_queue,
            parent_target_queue=executed_request.target_queue,
        )
        for dependency_ready_event in dependency_ready_events:
            yield dependency_ready_event

        # get resource and process dependencies after primitive dependencies are available
        dependency_ready_events = self.get_dependencies_for_execution(
            resource=executed_request.resource,
            relevant_dependencies=resource_dependencies + process_dependencies,
            requesting_item=executed_request.requesting_item,
            dependency_release_event=executed_request.completed,
        )
        for dependency_ready_event in dependency_ready_events:
            yield dependency_ready_event

    def request_buffering(self, executed_request: request.Request) -> Optional[events.Event]:
        buffer = self.interaction_handler.get_interaction_buffer(executed_request)
        if not buffer:
            return None
        transport_process_finished_event = self.request_transport(
            executed_request.requesting_item, buffer
        )
        executed_request.transport_to_target = transport_process_finished_event
        return transport_process_finished_event

    def execute_entity_routing(
        self, executed_request: request.Request
    ) -> Generator[None, None, None]:
        # Verify entity is available and in correct location before routing
        if executed_request.entity.bound:
            raise ValueError(f"Entity {executed_request.entity.data.ID} is already bound and cannot be routed")
        
        # Check if entity is in the queue at its current location
        if executed_request.entity._current_locatable is None:
            raise ValueError(f"Entity {executed_request.entity.data.ID} has no current location")
        
        # Verify entity is actually in the queue
        if hasattr(executed_request.entity._current_locatable, 'items'):
            if executed_request.entity.data.ID not in executed_request.entity._current_locatable.items:
                raise ValueError(f"Entity {executed_request.entity.data.ID} is not in queue {executed_request.entity._current_locatable.data.ID}")
        
        executed_request.entity.bind(
            executed_request.requesting_item, executed_request.resolved_dependency
        )
        # TODO: add here with interaction handler searching for interaction points
        # Get the target location for transport - this should be where the dependency will be used
        # For transport/production requests, dependencies should go to the origin_queue where processing starts
        # Prefer the origin_queue if it's set (passed from parent request), otherwise use requesting_item's location
        target_location = executed_request.origin_queue
        
        if target_location is None:
            # Fallback to requesting_item's current location
            target_location = executed_request.requesting_item._current_locatable
            
        # If requesting_item is a Lot and still no target, try primary entity's location
        if target_location is None and executed_request.requesting_item.type == EntityType.LOT:
            target_location = executed_request.requesting_item.get_primary_entity().current_locatable
        
        if target_location is None:
            raise ValueError(f"Cannot determine target location for dependency routing. Requesting item {executed_request.requesting_item.data.ID} has no current location and no origin_queue set.")
        
        trans_process_finished_event = self.request_transport(
            executed_request.entity, target_location
        )
        yield trans_process_finished_event
        # retrieve from queue after transport for binding
        # yield from executed_request.entity.current_locatable.get(executed_request.entity.data.ID)

        executed_request.completed.succeed()
        yield executed_request.dependency_release_event
        # Find an appropriate storage for the primitive
        # place in storage after releasing the dependency binding
        # After release, the entity should be at the parent request's target_queue (where it was unloaded)
        # The transport handler should have updated its location, but we ensure it's correct here
        if executed_request.resolved_dependency.data.dependency_type == DependencyType.TOOL:
            # The entity was unloaded at the target_queue of the parent request
            # Update its location to ensure it's correct (transport handler should have done this, but double-check)
            entity_release_location = executed_request.target_queue if executed_request.target_queue else target_location
            if entity_release_location:
                executed_request.entity._current_locatable = entity_release_location
            
            # Only transport back to storage if entity is not consumable
            for entity in executed_request.get_atomic_entities():
                if self._entity_becomes_consumable(entity):
                    continue
                target_storage = self._find_available_storage_for_primitive(executed_request.entity)
                # request_transport will handle getting the entity from its current_locatable
                transport_process_finished_event = self.request_transport(
                    executed_request.entity, target_storage
                )
                yield transport_process_finished_event
                executed_request.entity.release()
                self.free_primitives_by_type[executed_request.entity.data.type].append(
                    executed_request.entity
                )
                # Notify all resources that might be waiting for this primitive type
                # This allows controllers to recheck feasibility of pending requests
                for resource in self.resources:
                    if resource.controller and not resource.controller.state_changed.triggered:
                        resource.controller.state_changed.succeed()
        if not self.got_primitive_request.triggered:
            self.got_primitive_request.succeed()

    def _entity_becomes_consumable(self, entity: primitive.Primitive | product.Product) -> bool:
        """
        Only products expose the becomes_consumable flag. Treat everything else as reusable.
        """
        return entity.type == EntityType.PRODUCT and entity.data.becomes_consumable

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
            if free_requests[0].request_type in (request.RequestType.PROCESS_DEPENDENCY, request.RequestType.RESOURCE_DEPENDENCY):
                routing_heuristic = random_routing_heuristic
            else:
                routing_heuristic = free_requests[0].requesting_item.routing_heuristic
            routing_heuristic(free_requests)
        except Exception:
            def fallback_heuristic(x):
                return x[0]
            fallback_heuristic(free_requests)
        routed_request = free_requests.pop(0)
        return routed_request

    def get_dependencies_for_execution(
        self,
        resource: resources.Resource,
        relevant_dependencies: List[Dependency],
        requesting_item: Union[product.Product, primitive.Primitive],
        dependency_release_event: events.Event,
        parent_origin_queue: Optional[port.Queue] = None,
        parent_target_queue: Optional[port.Queue] = None,
    ) -> List[simpy.Event]:
        """
        Routes all dependencies for processing to a resource. Covers currently only primitive dependencies (workpiece carriers, e.g.)
        Args:
            resource (resources.Resource): The resource.
            parent_origin_queue: The origin_queue of the parent request (where the dependency will be picked up)
            parent_target_queue: The target_queue of the parent request (where the dependency will be unloaded and released)
        Returns:
            Generator[None, None, None]: A generator that yields when the dependencies are routed.
        """
        dependency_ready_events = []
        for dependency in relevant_dependencies:
            # Check if dependency is per_lot - if so, only request once regardless of lot size
            # For per_instance dependencies, request for each instance in the lot
            if hasattr(dependency.data, 'per_lot') and dependency.data.per_lot:
                # Per lot dependency - only request once
                request_info = self.request_handler.add_dependency_request(
                    requiring_dependency=resource,
                    requesting_item=requesting_item,
                    dependency=dependency,
                    dependency_release_event=dependency_release_event,
                    parent_origin_queue=parent_origin_queue,
                    parent_target_queue=parent_target_queue,
                )
                if not request_info:
                    continue
                if dependency.data.dependency_type == DependencyType.TOOL or dependency.data.dependency_type == DependencyType.ASSEMBLY:
                    if not self.got_primitive_request.triggered:
                        self.got_primitive_request.succeed()
                else:
                    if not self.got_requested.triggered:
                        self.got_requested.succeed()
                dependency_ready_events.append(request_info.request_completion_event)
            else:
                # Per instance dependency - request for each atomic entity
                # This maintains backward compatibility for dependencies without per_lot attribute
                request_info = self.request_handler.add_dependency_request(
                    requiring_dependency=resource,
                    requesting_item=requesting_item,
                    dependency=dependency,
                    dependency_release_event=dependency_release_event,
                    parent_origin_queue=parent_origin_queue,
                    parent_target_queue=parent_target_queue,
                )
                if not request_info:
                    continue
                if dependency.data.dependency_type == DependencyType.TOOL or dependency.data.dependency_type == DependencyType.ASSEMBLY:
                    if not self.got_primitive_request.triggered:
                        self.got_primitive_request.succeed()
                else:
                    if not self.got_requested.triggered:
                        self.got_requested.succeed()
                dependency_ready_events.append(request_info.request_completion_event)
        return dependency_ready_events

    def request_processing(self, product_instance: product.Product) -> request.Request:
        origin = product_instance.current_locatable
        origin_queue = product_instance.current_locatable
        target = self._determine_sink_for_product(product_instance)
        target_queue = target.ports[0]

        processing_request, request_info = self.request_handler.add_process_model_request(
            entity=product_instance,
            process_model=product_instance.process_model,
            system_resource=self.resource_factory.global_system_resource,
            origin=origin,
            origin_queue=origin_queue,
            target=target,
            target_queue=target_queue,
        )
        self.request_handler.mark_routing(processing_request, setting_current_process=False)
        self.resource_factory.global_system_resource.controller.request(processing_request)
        # Handle dependencies for process model requests
        if processing_request.required_dependencies:
            self.env.process(self._handle_process_model_dependencies(processing_request))
        return processing_request
    
    def _handle_process_model_dependencies(self, processing_request: request.Request) -> Generator:
        """
        Handles dependencies for process model requests by waiting for dependencies_requested event
        and then routing the dependencies.
        """
        yield processing_request.dependencies_requested
        dependency_ready_events = []
        for dependency in processing_request.required_dependencies:
            request_info = self.request_handler.add_dependency_request(
                requiring_dependency=processing_request.requesting_item,
                requesting_item=processing_request.requesting_item,
                dependency=dependency,
                dependency_release_event=processing_request.completed,
            )
            if not request_info:
                continue
            if dependency.data.dependency_type == DependencyType.TOOL or dependency.data.dependency_type == DependencyType.ASSEMBLY:
                if not self.got_primitive_request.triggered:
                    self.got_primitive_request.succeed()
            dependency_ready_events.append(request_info.request_completion_event)
        for dependency_ready_event in dependency_ready_events:
            yield dependency_ready_event
        processing_request.dependencies_ready.succeed()

    def request_process_step(self, product: product.Product, next_possible_processes: List[process.PROCESS_UNION]) -> events.Event:
        """
        Routes a product to perform the next process by assigning a production resource, that performs the process, to the product
        and assigning a transport resource to transport the product to the next process.

        Args:
            product (product.Product): The product.

        Returns:
            Generator[Tuple[request.Request, request.TransportResquest]]: A generator that yields when the product is routed.
        """
        process_event = self.request_handler.add_product_requests(
            product, next_possible_processes
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

    def _determine_sink_for_product(self, product: product.Product) -> sink.Sink:
        """
        Determines a sink for a product.
        """
        possible_sinks = self.sink_factory.get_sinks_with_product_type(
            product.data.type
        )
        return random.choice(possible_sinks)

    def route_disassembled_product_to_sink(self, product: product.Product)-> sink.Sink:
        possible_sinks = self.sink_factory.get_sinks_with_product_type(
            product.data.type
        )
        chosen_sink = random.choice(possible_sinks)
        target_port = chosen_sink.ports[0]
        product.update_location(target_port)
        return chosen_sink

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

from prodsys.simulation import request
from prodsys.simulation.entities import primitive
