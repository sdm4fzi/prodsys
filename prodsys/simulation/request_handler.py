from __future__ import annotations

from typing import Deque, List, TYPE_CHECKING, Literal, Optional, Union, Dict, Set
from dataclasses import dataclass, field

import logging

import simpy

from prodsys.simulation.process_matcher import ProcessMatcher

logger = logging.getLogger(__name__)


from prodsys.simulation import primitive, resources
from prodsys.simulation import request


if TYPE_CHECKING:
    from prodsys.simulation import resources, product, process
    from prodsys.simulation.product import Locatable

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


@dataclass
class RequestHandler:
    """
    Handles requests, determines additional required requests, and manages request allocation efficiently.
    """

    process_matcher: ProcessMatcher

    request_infos: dict[RequestInfoKey, RequestInfo] = field(default_factory=dict)
    pending_requests: list[RequestInfoKey] = field(default_factory=list)

    def add_product_requests(
        self, item: Union[product.Product, primitive.Primitive]
    ) -> RequestInfo:
        """
        Adds a new request to the pending requests.

        Args:
            item (Union[product.Product, auxiliary.Auxiliary]): The item making the request.
            possible_resources_and_processes (List[Tuple[resources.Resource, process.PROCESS_UNION]]):
                List of possible resources and processes that can handle the request.
            process (Optional[process.PROCESS_UNION]): The process to be executed, defaults to item's next_possible_processes.
        """
        request_info_key = get_request_info_key(item)
        possible_resources_and_processes = self.process_matcher.get_compatible(
            item.next_possible_processes, item.data.type
        )
        resources = {}
        for resource, process_instance in possible_resources_and_processes:
            resource_id = resource.data.ID
            if resource_id not in resources:
                resources[resource_id] = []
            resources[resource_id].append(process_instance)

        if hasattr(item, "product_data"):
            request_type = request.RequestType.PRODUCTION
        else:
            request_type = request.RequestType.AUXILIARY

        request_completion_event = simpy.Event(item.env)
        request_info = RequestInfo(
            key=request_info_key,
            item=item,
            resource_mappings=resources,
            request_type=request_type,
            origin=None,
            target=None,
            request_state="pending",
            request_completion_event=request_completion_event,
        )
        # Add to pending requests
        self.request_infos[request_info_key] = request_info
        self.pending_requests.append(request_info_key)
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
        self.pending_requests.append(request_info_key)
        return request_info

    def mark_routing(self, allocated_request: request.Request) -> None:
        """
        Marks a request as allocated to a resource.

        Args:
            allocated_request (request.Request): The request that has been allocated.
        """
        if allocated_request.request_type == request.RequestType.TRANSPORT:
            request_info_key = get_transport_request_info_key(
                allocated_request.item,
                allocated_request.origin,
                allocated_request.target,
            )
        else:
            request_info_key = get_request_info_key(allocated_request.item)
        allocated_request.product.current_process = allocated_request.process
        self.request_infos[request_info_key].request_state = "routed"

    def mark_completion(self, completed_request: request.Request) -> None:
        """
        Marks a request as completed.

        Args:
            completed_request (request.Request): The request that has been completed.
        """
        if completed_request.request_type == request.RequestType.TRANSPORT:
            request_info_key = get_transport_request_info_key(
                completed_request.item,
                completed_request.origin,
                completed_request.target,
            )
        else:
            request_info_key = get_request_info_key(completed_request.item)
        self.request_infos[request_info_key].request_state = "completed"

    def create_request(
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
        if request_info.request_type == request.RequestType.TRANSPORT:
            route = self.process_matcher.get_route(
                request_info.origin, request_info.target, process
            )
        else:
            route = None

        return request.Request(
            item=request_info.item,
            resource=resource,
            process=process,
            origin=request_info.origin,
            target=request_info.target,
            request_type=request_info.request_type,
            completed=request_info.request_completion_event,
            route=route,
        )

    def get_next_product_to_route(
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
        self.current_request_index = 0
        for request_info_index in range(
            self.current_request_index, len(self.pending_requests)
        ):
            request_info_key = self.pending_requests[request_info_index]
            request_info = self.request_infos[request_info_key]
            possible_resources_and_processes = request_info.resource_mappings
            requests = []
            for free_resource_index, free_resource_id in free_resources_set:
                if free_resource_id in possible_resources_and_processes:
                    for process_instance in possible_resources_and_processes[
                        free_resource_id
                    ]:
                        free_resource = free_resources[free_resource_index]
                        new_request = self.create_request(
                            request_info,
                            free_resource,
                            process_instance,
                        )
                        requests.append(new_request)

            if requests:
                self.pending_requests.remove(request_info_key)
                return requests
