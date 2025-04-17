from __future__ import annotations

from typing import Deque, List, TYPE_CHECKING, Literal, Optional, Union, Dict, Set
from dataclasses import dataclass, field

import logging

import simpy

from prodsys.simulation.process_matcher import ProcessMatcher, get_process_signature

logger = logging.getLogger(__name__)


from prodsys.simulation import resources
from prodsys.simulation import request


if TYPE_CHECKING:
    from prodsys.simulation import resources, product, auxiliary, process
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
    item: Union[product.Product, auxiliary.Auxiliary]
    resource_mappings: dict[ResourceIdentifier, list[process.PROCESS_UNION]]
    request_type: request.RequestType

    origin: Optional[Locatable]
    target: Optional[Locatable]

    request_completion_event: simpy.Event

    request_state: Literal["pending", "routed", "completed"]


def get_request_info_key(item: Union[product.Product, auxiliary.Auxiliary]):
    item_id = item.product_data.ID
    if hasattr(item, "next_possible_processes"):
        process_id = hash(
            tuple(process.process_data.ID for process in item.next_possible_processes)
        )
    else:
        process_id = ""
    return f"{item_id}:{process_id}"


@dataclass
class RequestHandler:
    """
    Handles requests, determines additional required requests, and manages request allocation efficiently.
    """

    process_matcher: ProcessMatcher

    request_infos: dict[RequestInfoKey, RequestInfo] = field(default_factory=dict)
    pending_requests: list[RequestInfoKey] = field(default_factory=list)

    def add_product_requests(
        self, item: Union[product.Product, auxiliary.Auxiliary]
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
            [item.next_prodution_process], item.product_data.product_type
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
        item: Union[product.Product, auxiliary.Auxiliary],
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
        request_info_key = get_request_info_key(item)
        possible_resources_and_processes = (
            self.process_matcher.get_transport_compatible(
                origin, target, get_process_signature(item.transport_process)
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
        request_info_key = get_request_info_key(allocated_request.item)
        self.request_infos[request_info_key].request_state = "routed"

    def mark_completion(self, completed_request: request.Request) -> None:
        """
        Marks a request as completed.

        Args:
            completed_request (request.Request): The request that has been completed.
        """
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
        return request.Request(
            item=request_info.item,
            resource=resource,
            process=process,
            origin=request_info.origin,
            target=request_info.target,
            request_type=request_info.request_type,
            completed=request_info.request_completion_event,
        )


    def get_possible_production_requests(self, product_instance: product.Product) -> List[request.Request]:
        possible_requests = []
        possible_resources_and_processes = self.process_matcher.get_compatible(
            [product_instance.next_prodution_process], product_instance.product_data.product_type
        )
        for resource, process_instance in possible_resources_and_processes:
            new_request = request.Request(
                process=process_instance,
                product=product_instance,
                resource=resource,
            )
            possible_requests.append(
                new_request
            )
        return possible_requests
    

    def get_possible_transport_requests(
        self,
        product_instance: product.Product,
        target: Locatable,
    ) -> List[request.Request]:
        possible_requests = []
        possible_resources_and_processes = self.process_matcher.get_transport_compatible(
            product_instance.current_locatable, target, get_process_signature(product_instance.transport_process)
        )
        for resource, process_instance in possible_resources_and_processes:
            new_request = request.TransportResquest(
                product=product_instance,
                target=target,
                resource=resource,
                process=process_instance,
                origin=product_instance.current_locatable,
            )
            route_key = (
                resource.data.ID,
                target.data.ID,
                get_process_signature(process_instance),
            )
            route = self.process_matcher.route_cache.get(route_key, None)
            if route is None:
                raise ValueError(
                    f"Route not found in cache for key {route_key}. Ensure the route is properly cached."
                )
            new_request.route = route
            possible_requests.append(new_request)

        return possible_requests
        

    # def get_transport_requests_for_product()

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
