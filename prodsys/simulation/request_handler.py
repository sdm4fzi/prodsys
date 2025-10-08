from __future__ import annotations

from typing import Deque, List, TYPE_CHECKING, Literal, Optional, Union, Dict, Set
from dataclasses import dataclass, field

import logging

import simpy

from prodsys.models.dependency_data import DependencyType
from prodsys.simulation.dependency import DependedEntity, Dependency
from prodsys.simulation.process import DependencyProcess
from prodsys.simulation.process_matcher import ProcessMatcher

logger = logging.getLogger(__name__)


from prodsys.simulation import resources
from prodsys.simulation.entities import primitive
from prodsys.simulation import request


if TYPE_CHECKING:
    from prodsys.simulation import resources, process
    from prodsys.simulation.locatable import Locatable
    from prodsys.simulation.entities import product

    # from prodsys.factories.source_factory import SourceFactory

RequestInfoKey = str
ResourceIdentifier = str


@dataclass()
class RequestInfo:
    """
    Represents a key for mapping requests to resources.

    Attributes:
        request_id (str): Unique identifier for the request.
        resource_id (str): Unique identifier for the resource.
    """

    key: str
    item: Union[product.Product, primitive.Primitive]
    resource_mappings: dict[ResourceIdentifier, list[process.PROCESS_UNION]]
    request_type: request.RequestType

    origin: Optional[Locatable]
    target: Optional[Locatable]
    request_completion_event: simpy.Event
    request_state: Literal["pending", "routed", "completed"]

    dependency: Optional[Dependency] = None

    dependency_release_event: Optional[simpy.Event] = None


def get_request_info_key(item: Union[product.Product, primitive.Primitive]):
    item_id = item.data.ID
    if hasattr(item, "next_possible_processes"):
        process_id = hash(
            tuple(process.data.ID for process in item.next_possible_processes)
        )
    else:
        process_id = ""
    return f"{item_id}:{process_id}"


def get_transport_request_info_key(
    item: Union[product.Product, primitive.Primitive],
    origin: Locatable,
    target: Locatable,
):
    item_id = item.data.ID
    origin_id = origin.data.ID
    target_id = target.data.ID
    return f"{item_id}:{origin_id}:{target_id}"


def get_dependency_request_info_key(
    dependency_item: Union[product.Product, resources.Resource],
    dependency: Dependency,
    requesting_item: Union[product.Product, resources.Resource] = None,
):
    item_id = dependency_item.data.ID
    dependency_id = dependency.data.ID
    if requesting_item is not None:
        item_id = requesting_item.data.ID
    else:
        item_id = dependency_item.data.ID
    # FIXME: consider here product or so, double item_id makes no sense
    return f"{item_id}:{dependency_id}:{item_id}"


@dataclass
class RequestHandler:
    """
    Handles requests, determines additional required requests, and manages request allocation efficiently.
    """

    process_matcher: ProcessMatcher

    request_infos: dict[RequestInfoKey, RequestInfo] = field(default_factory=dict)
    pending_resource_requests: list[RequestInfoKey] = field(default_factory=list)
    pending_primitive_requests: list[RequestInfoKey] = field(default_factory=list)

    pending_requests: dict[str, RequestInfo] = field(default_factory=dict)
    routed_requests: dict[str, RequestInfo] = field(default_factory=dict)

    
    def add_process_model_request(
        self, entity: Union[product.Product, primitive.Primitive], 
        process_model: process.ProcessModelProcess,
        system_resource: resources.Resource,
        target: Locatable,
        target_queue: Locatable,
    ) -> tuple[request.Request, RequestInfo]:
        """
        Adds a new request to the pending requests.
        """
        dependencies = []
        if entity.dependencies:
            dependencies.extend(entity.dependencies)
        if process_model.dependencies:
            dependencies.extend(process_model.dependencies)
        if system_resource.dependencies:
            dependencies.extend(system_resource.dependencies)
        request_info_key = get_request_info_key(entity)
        request_completion_event = simpy.Event(entity.env)
        request_info = RequestInfo(
            key=request_info_key,
            item=entity,
            resource_mappings={process_model.data.ID: [process_model]},
            request_type=request.RequestType.PROCESS_MODEL,
            origin=None,
            target=None,
            request_state="pending",
            request_completion_event=request_completion_event,
        )
        # Add to pending requests
        self.request_infos[request_info_key] = request_info
        self.pending_requests[request_info_key] = request_info
        processing_request = request.Request(
            requesting_item=entity,
            entity=entity,
            # TODO: make sure that request handler makes this request type also for nested process models!
            request_type=request.RequestType.PROCESS_MODEL,
            process=entity.process_model,
            resource=system_resource,
            origin=entity.current_locatable,
            target=target,
            origin_queue=entity.current_locatable,
            target_queue=target_queue,
            completed=request_completion_event,
            required_dependencies=dependencies,
        )
        self.pending_requests[id(processing_request.completed)] = request_info
        self.request_infos[request_info_key] = request_info
        return processing_request, request_info

    def add_product_requests(
        self, entity: Union[product.Product, primitive.Primitive], 
        next_possible_processes: List[process.PROCESS_UNION],
    ) -> RequestInfo:
        """
        Adds a new request to the pending requests.

        Args:
            item (Union[product.Product, auxiliary.Auxiliary]): The item making the request.
            possible_resources_and_processes (List[Tuple[resources.Resource, process.PROCESS_UNION]]):
                List of possible resources and processes that can handle the request.
            process (Optional[process.PROCESS_UNION]): The process to be executed, defaults to item's next_possible_processes.
        """
        request_info_key = get_request_info_key(entity)
        possible_resources_and_processes = self.process_matcher.get_compatible(
            next_possible_processes
        )
        resources = {}
        for resource, process_instance in possible_resources_and_processes:
            resource_id = resource.data.ID
            if resource_id not in resources:
                resources[resource_id] = []
            resources[resource_id].append(process_instance)

        if hasattr(entity, "process_model"):
            request_type = request.RequestType.PRODUCTION
        else:
            request_type = request.RequestType.PRIMITIVE_DEPENDENCY

        request_completion_event = simpy.Event(entity.env)
        request_info = RequestInfo(
            key=request_info_key,
            item=entity,
            resource_mappings=resources,
            request_type=request_type,
            origin=None,
            target=None,
            request_state="pending",
            request_completion_event=request_completion_event,
        )
        # Add to pending requests
        self.request_infos[request_info_key] = request_info
        self.pending_resource_requests.append(request_info_key)
        return request_info

    def add_transport_request(
        self,
        item: Union[product.Product, primitive.Primitive],
        target: Locatable,
    ) -> RequestInfo:
        """
        Adds a new transport request to the pending requests.

        Args:
            item (Union[product.Product, auxiliary.Auxiliary]): The item to transport.
            origin (Locatable): The origin location.
            target (Locatable): The target location.
            possible_resources_and_processes (List[Tuple[resources.Resource, process.PROCESS_UNION]]):
                List of possible transport resources and processes.
        """
        origin = item.current_locatable
        request_info_key = get_transport_request_info_key(
            item,
            origin,
            target,
        )
        possible_resources_and_processes = (
            self.process_matcher.get_transport_compatible(
                origin, target, item.transport_process.get_process_signature()
            )
        )
        if not possible_resources_and_processes:
            raise ValueError(f"No resource available for transport of item {item.data.ID} with process {item.data.transport_process}")
        resources = {}
        for resource, process_instance in possible_resources_and_processes:
            resource_id = resource.data.ID
            if resource_id not in resources:
                resources[resource_id] = []
            resources[resource_id].append(process_instance)

        request_completion_event = simpy.Event(item.env)

        request_info = RequestInfo(
            key=request_info_key,
            item=item,
            resource_mappings=resources,
            request_type=request.RequestType.TRANSPORT,
            origin=origin,
            target=target,
            request_state="pending",
            request_completion_event=request_completion_event,
        )
        # Add to pending requests
        self.request_infos[request_info_key] = request_info
        self.pending_resource_requests.append(request_info_key)
        return request_info

    def add_dependency_request(
        self,
        requiring_dependency: Union[product.Product, resources.Resource],
        requesting_item: Union[product.Product, resources.Resource],
        dependency: Dependency,
        dependency_release_event: Optional[simpy.Event] = None,
    ) -> RequestInfo:
        """
        Adds a new dependency request to the pending requests.

        Args:
            requesting_item (Union[product.Product, resources.Resource]): The item making the request.
            dependency (DependedEntity): The dependency to be fulfilled.
        """
        if dependency.data.dependency_type == DependencyType.PRIMITIVE:
            request_type = request.RequestType.PRIMITIVE_DEPENDENCY
            resource_mappings = {}
            requiring_dependency = requesting_item
        elif dependency.data.dependency_type == DependencyType.RESOURCE:
            request_type = request.RequestType.RESOURCE_DEPENDENCY
            resource_mappings = {
                dependency.required_resource.data.ID: [DependencyProcess()]
            }
        elif dependency.data.dependency_type == DependencyType.PROCESS:
            request_type = request.RequestType.PROCESS_DEPENDENCY
            possible_resourcs = self.process_matcher.get_compatible(
                [dependency.required_process]
            )
            resource_mappings = {}
            for resource, process_instance in possible_resourcs:
                resource_id = resource.data.ID
                if resource_id in resource_mappings:
                    continue
                resource_mappings[resource_id] = [DependencyProcess()]
        elif dependency.data.dependency_type == DependencyType.LOT:
            return
        else:
            raise ValueError(
                f"Unknown dependency type: {dependency.data.dependency_type}"
            )

        request_completion_event = simpy.Event(requiring_dependency.env)
        request_info_key = get_dependency_request_info_key(
            requiring_dependency, dependency, requesting_item
        )

        request_info = RequestInfo(
            key=request_info_key,
            item=requiring_dependency,
            resource_mappings=resource_mappings,
            request_type=request_type,
            request_state="pending",
            request_completion_event=request_completion_event,
            dependency=dependency,
            dependency_release_event=dependency_release_event,
            origin=None,
            target=None,
        )
        self.request_infos[request_info_key] = request_info
        if dependency.data.dependency_type == DependencyType.PRIMITIVE:
            self.pending_primitive_requests.append(request_info_key)
        else:
            self.pending_resource_requests.append(request_info_key)
        return request_info

    def mark_routing(self, allocated_request: request.Request) -> None:
        """
        Marks a request as allocated to a resource.

        Args:
            allocated_request (request.Request): The request that has been allocated.
        """
        if allocated_request.request_type == request.RequestType.PRODUCTION:
            allocated_request.requesting_item.current_process = (
                allocated_request.process
            )

        request_info = self.pending_requests.pop(id(allocated_request.completed), None)
        if not request_info:
            raise ValueError(
                f"Request info not found for completed request {allocated_request.completed}"
            )
        request_info.request_state = "routed"
        self.routed_requests[id(allocated_request.completed)] = request_info

    def mark_completion(self, completed_request: request.Request) -> None:
        """
        Marks a request as completed.

        Args:
            completed_request (request.Request): The request that has been completed.
        """
        request_info = self.routed_requests.pop(id(completed_request.completed), None)
        if not request_info:
            raise ValueError(
                f"Request info not found for completed request {completed_request.completed}"
            )
        request_info.request_state = "completed"

    def create_resource_request(
        self,
        request_info: RequestInfo,
        resource: resources.Resource,
        process: process.PROCESS_UNION,
    ) -> request.Request:
        """
        Creates a new request for the given resource and process.

        Args:
            request_info (RequestInfo): The request information.
            resource (resources.Resource): The resource to handle the request.
            process (process.PROCESS_UNION): The process to be executed.

        Returns:
            request.Request: The created request.
        """
        dependencies = resource.dependencies + process.dependencies
        request_instance = request.Request(
            requesting_item=request_info.item,
            entity=request_info.item,
            resource=resource,
            process=process,
            origin=request_info.origin,
            target=request_info.target,
            request_type=request_info.request_type,
            completed=request_info.request_completion_event,
            resolved_dependency=request_info.dependency,
            dependency_release_event=request_info.dependency_release_event,
            required_dependencies=dependencies,
        )
        return request_instance

    def get_next_resource_request_to_route(
        self, free_resources: list[resources.Resource]
    ) -> Optional[List[request.Request]]:
        """
        Returns a list of all pending requests that can be allocated.

        Returns:
            List[request.Request]: List of free requests ready for allocation.
        """
        free_resources_set = set(
            (index, resource.data.ID) for index, resource in enumerate(free_resources)
        )
        self.current_resource_request_index = 0
        for request_info_index in range(
            self.current_resource_request_index, len(self.pending_resource_requests)
        ):
            request_info_key = self.pending_resource_requests[request_info_index]
            request_info = self.request_infos[request_info_key]
            possible_resources_and_processes = request_info.resource_mappings
            requests = []
            for free_resource_index, free_resource_id in free_resources_set:
                if free_resource_id in possible_resources_and_processes:
                    for process_instance in possible_resources_and_processes[
                        free_resource_id
                    ]:
                        free_resource = free_resources[free_resource_index]
                        new_request = self.create_resource_request(
                            request_info,
                            free_resource,
                            process_instance,
                        )
                        requests.append(new_request)

            if requests:
                self.pending_requests[id(requests[0].completed)] = request_info
                self.pending_resource_requests.remove(request_info_key)
                return requests

    def create_primitive_request(
        self,
        request_info: RequestInfo,
        primitive: primitive.Primitive,
    ) -> request.Request:
        """
        Creates a new request for the given primitive and process.

        Args:
            request_info (RequestInfo): The request information.
            primitive (primitive.Primitive): The primitive to handle the request.
            process (process.PROCESS_UNION): The process to be executed.

        Returns:
            request.Request: The created request.
        """
        return request.Request(
            requesting_item=request_info.item,
            entity=primitive,
            process=DependencyProcess(),
            request_type=request_info.request_type,
            completed=request_info.request_completion_event,
            resolved_dependency=request_info.dependency,
            dependency_release_event=request_info.dependency_release_event,
        )

    def get_next_primitive_request_to_route(
        self, free_primitives: dict[str, list[primitive.Primitive]]
    ) -> Optional[List[request.Request]]:
        """
        Returns a list of all pending requests that can be allocated.

        Returns:
            List[request.Request]: List of free requests ready for allocation.
        """
        if not self.pending_primitive_requests:
            return None
        self.current_primitive_request_index = 0
        for request_info_index in range(
            self.current_primitive_request_index, len(self.pending_primitive_requests)
        ):
            request_info_key = self.pending_primitive_requests[request_info_index]
            request_info = self.request_infos[request_info_key]
            possible_primitives = free_primitives.get(
                request_info.dependency.required_primitive.data.type, []
            )
            possible_primitive_requests = []
            for possible_primitive in possible_primitives:
                new_request = self.create_primitive_request(
                    request_info,
                    possible_primitive,
                )
                possible_primitive_requests.append(new_request)
            if possible_primitive_requests:
                self.pending_primitive_requests.remove(request_info_key)
                # self.request_infos.pop(request_info_key, None)
                self.pending_requests[id(possible_primitive_requests[0].completed)] = (
                    request_info
                )
                return possible_primitive_requests

    def get_rework_processes(
        self, failed_process: process.PROCESS_UNION
    ) -> List[process.PROCESS_UNION]:
        """
        Returns a list of rework processes for the given item.

        Args:
            item (Union[product.Product, primitive.Primitive]): The item to get rework processes for.

        Returns:
            List[process.PROCESS_UNION]: List of rework processes.
        """
        return self.process_matcher.get_rework_compatible(
            failed_process
        )