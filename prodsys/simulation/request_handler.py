from __future__ import annotations

from typing import Deque, List, TYPE_CHECKING, Union, Dict, Set
from dataclasses import dataclass, field

import logging

from prodsys.simulation.process_matcher import ProcessMatcher


logger = logging.getLogger(__name__)


from prodsys.simulation import resources
from prodsys.simulation import request


if TYPE_CHECKING:
    from prodsys.simulation import resources, product, auxiliary, process
    from prodsys.simulation.product import Locatable

    # from prodsys.factories.source_factory import SourceFactory

RequestIdentifier = str
ResourceIdentifier = str


@dataclass(frozen=True)
class RequestIdentifier:
    """
    Represents a key for mapping requests to resources.

    Attributes:
        request_id (str): Unique identifier for the request.
        resource_id (str): Unique identifier for the resource.
    """
    item: str
    transport_requests_per_resource: Dict[str, List[request.Request]] = field(
        default_factory=dict
    )
    process_requests_per_resource: Dict[str, List[request.Request]] = field(
        default_factory=dict
    )

@dataclass
class RequestHandler:
    """
    Handles requests, determines additional required requests, and manages request allocation efficiently.
    """

    # TODO: Make data storage here more efficient! save free resources in dict and make requests mapped to these resources.
    process_matcher: ProcessMatcher

    free_resources: list[ResourceIdentifier] = field(default_factory=list)
    # Maps request keys to lists of pending requests
    pending_requests: Deque[RequestIdentifier] = field(default_factory=lambda: Deque())
    # Maps request keys to allocated requests
    allocated_requests: Dict[str, request.Request] = field(default_factory=dict)
    # Set of completed request keys
    completed_requests: Set[str] = field(default_factory=set)
    # Maps resource IDs to lists of requests that can be handled by the resource
    resource_to_requests: Dict[str, List[request.Request]] = field(default_factory=dict)

    def add_product_requests(
        self, item: Union[product.Product, auxiliary.Auxiliary]
    ) -> None:
        """
        Adds a new request to the pending requests.

        Args:
            item (Union[product.Product, auxiliary.Auxiliary]): The item making the request.
            possible_resources_and_processes (List[Tuple[resources.Resource, process.PROCESS_UNION]]):
                List of possible resources and processes that can handle the request.
            process (Optional[process.PROCESS_UNION]): The process to be executed, defaults to item's next_possible_processes.
        """
        item_id = item.data.ID
        requested_process = process if process else item.next_possible_processes
        process_id = requested_process.get_process_signature()
        key = f"{item_id}:{process_id}"

        # Create requests for each possible resource and process
        new_requests = []
        possible_resources_and_processes = self.process_matcher.get_compatible(
            item.next_possible_processes
        )
        for resource, process_instance in possible_resources_and_processes:
            # Create request that are necessary and need to performed before (e.g. transport)
            if isinstance(item, product.Product):
                new_request = request.Request(
                    request_type=request.RequestType.PRODUCTION,
                    process=process_instance,
                    resource=resource,
                    item=item,
                )
            else:  # Auxiliary
                new_request = request.Request(
                    request_type=request.RequestType.AUXILIARY,
                    process=process_instance,
                    resource=resource,
                    item=item,
                )

            new_request.set_process(process_instance)
            new_requests.append(new_request)

            # Map resource to request for quick lookup
            resource_id = resource.data.ID
            if resource_id not in self.resource_to_requests:
                self.resource_to_requests[resource_id] = []
            self.resource_to_requests[resource_id].append(new_request)

        # Add to pending requests
        self.pending_requests.append(new_requests)

    def add_transport_request(
        self,
        item: Union[product.Product, auxiliary.Auxiliary],
        target: Locatable,
    ) -> None:
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
        item_id = item.data.ID
        origin_id = origin.data.ID
        target_id = target.data.ID
        key = f"transport:{item_id}:{origin_id}:{target_id}"

        # Create transport requests for each possible resource and process
        possible_resources_and_processes = (
            self.process_matcher.get_transport_compatible(item.transport_process)
        )
        new_requests = []
        for resource, process_instance in possible_resources_and_processes:
            new_request = request.Request(
                process=process_instance,
                item=item,
                resource=resource,
                origin=origin,
                target=target,
                request_type=request.RequestType.TRANSPORT,
            )
            new_requests.append(new_request)

            # Map resource to request for quick lookup
            resource_id = resource.data.ID
            if resource_id not in self.resource_to_requests:
                self.resource_to_requests[resource_id] = []
            self.resource_to_requests[resource_id].append(new_request)

        # Add to pending requests
        self.pending_requests.append(new_requests)

    def mark_allocation(self, allocated_request: request.Request) -> None:
        """
        Marks a request as allocated to a resource.

        Args:
            allocated_request (request.Request): The request that has been allocated.
        """
        if hasattr(allocated_request, "product") and allocated_request.product:
            item = allocated_request.product
        elif hasattr(allocated_request, "auxiliary") and allocated_request.auxiliary:
            item = allocated_request.auxiliary
        else:
            item = allocated_request.item

        item_id = item.data.ID
        process_id = allocated_request.process.get_process_signature()

        # Handle transport requests specially
        if hasattr(allocated_request, "origin") and hasattr(
            allocated_request, "target"
        ):
            origin_id = allocated_request.origin.data.ID
            target_id = allocated_request.target.data.ID
            key = f"transport:{item_id}:{origin_id}:{target_id}"
        else:
            key = f"{item_id}:{process_id}"

        # Store the allocated request
        self.allocated_requests[key] = allocated_request

        # Update resource to request mapping
        resource_id = allocated_request.resource.data.ID
        if resource_id in self.resource_to_requests:
            self.resource_to_requests[resource_id] = [
                req
                for req in self.resource_to_requests[resource_id]
                if not self._is_same_request(req, allocated_request)
            ]

    def mark_completion(self, completed_request: request.Request) -> None:
        """
        Marks a request as completed.

        Args:
            completed_request (request.Request): The request that has been completed.
        """
        if hasattr(completed_request, "product") and completed_request.product:
            item = completed_request.product
        elif hasattr(completed_request, "auxiliary") and completed_request.auxiliary:
            item = completed_request.auxiliary
        else:
            item = completed_request.item

        item_id = item.data.ID
        process_id = completed_request.process.get_process_signature()

        # Handle transport requests specially
        if hasattr(completed_request, "origin") and hasattr(
            completed_request, "target"
        ):
            origin_id = completed_request.origin.data.ID
            target_id = completed_request.target.data.ID
            key = f"transport:{item_id}:{origin_id}:{target_id}"
        else:
            key = f"{item_id}:{process_id}"

        # Move from allocated to completed
        if key in self.allocated_requests:
            self.allocated_requests.pop(key)

        # Mark as completed
        self.completed_requests.add(key)

    def get_next_product_to_route(self) -> List[request.Request]:
        """
        Returns a list of all pending requests that can be allocated.

        Returns:
            List[request.Request]: List of free requests ready for allocation.
        """        
        allocation_item = self.pending_requests.popleft()
        # assert that any of the resources is free, otherwise get next item
        
        return allocation_item

    def get_requests_for_resource(
        self, resource: resources.Resource
    ) -> List[request.Request]:
        """
        Returns all pending requests that can be handled by the given resource.

        Args:
            resource (resources.Resource): The resource to find requests for.

        Returns:
            List[request.Request]: List of requests that can be handled by the resource.
        """
        resource_id = resource.data.ID
        return self.resource_to_requests.get(resource_id, [])

    def _is_same_request(self, req1: request.Request, req2: request.Request) -> bool:
        """
        Checks if two requests are essentially the same (refer to the same item and process).

        Args:
            req1 (request.Request): First request.
            req2 (request.Request): Second request.

        Returns:
            bool: True if the requests are the same, False otherwise.
        """
        # Extract items from both requests
        if hasattr(req1, "product") and req1.product:
            item1 = req1.product
        elif hasattr(req1, "auxiliary") and req1.auxiliary:
            item1 = req1.auxiliary
        else:
            item1 = req1.item

        if hasattr(req2, "product") and req2.product:
            item2 = req2.product
        elif hasattr(req2, "auxiliary") and req2.auxiliary:
            item2 = req2.auxiliary
        else:
            item2 = req2.item

        # Check if same item and process
        return item1 == item2 and req1.process == req2.process
