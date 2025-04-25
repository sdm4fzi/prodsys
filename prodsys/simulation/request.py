from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Optional, List

import simpy


if TYPE_CHECKING:
    from prodsys.simulation.product import Product, Locatable
    from prodsys.simulation.process import (
        PROCESS_UNION,
        TransportProcess,
        LinkTransportProcess,
        CapabilityProcess,
        ProductionProcess,
    )
    from prodsys.simulation.auxiliary import Auxiliary

    from prodsys.simulation.resources import Resource
    from prodsys.simulation.store import Store, Queue


class RequestType(Enum):
    """
    Enum to represent the type of request.

    Attributes:
        TRANSPORT: Represents a transport request.
        MOVE: Represents a move request.
        REWORK: Represents a rework request.
        AUXILIARY_TRANSPORT: Represents an auxiliary transport request.
    """
    TRANSPORT = "transport"
    MOVE = "move"
    REWORK = "rework"
    PRODUCTION = "production"
    AUXILIARY = "auxiliary"


class Request:
    """
    Class to represents requests of a product for a process to be executed by a resource.

    Args:
        request_type (RequestType): Type of the request.
        process (process.PROCESS_UNION): The process.
        resource (resources.Resource): The resource.
        item (Optional[Locatable]): The item (product or auxiliary) making the request.
        origin_queue (Optional[Queue]): The origin queue.
        target_queue (Optional[Store]): The target queue.
        origin (Optional[Locatable]): The origin location for transport.
        target (Optional[Locatable]): The target location for transport.
    """

    def __init__(
        self,
        request_type: RequestType,
        process: PROCESS_UNION,
        resource: Resource,
        item: Optional[Product | Auxiliary] = None,
        origin_queue: Optional[Queue] = None,
        target_queue: Optional[Store] = None,
        origin: Optional[Locatable] = None,
        target: Optional[Locatable] = None,
        completed: Optional[simpy.Event] = None,
        route: Optional[List[Locatable]] = None,
    ):
        self.request_type = request_type
        self.process = process
        self.item = item
        self.resource = resource
        self.origin = origin
        self.target = target
        self.origin_queue: Optional[Queue] = origin_queue
        self.target_queue: Optional[Store] = target_queue
        self.completed = completed

        self.transport_to_target: Optional[simpy.Event] = None
        self.auxiliaries_ready: Optional[simpy.Event] = None

        # For compatibility with existing code
        if hasattr(item, 'product_data'):
            self.product = item
        else:
            self.product = None

        self.route: Optional[List[Locatable]] = route

        # For auxiliary requests
        self.auxiliary = None
        if request_type == RequestType.AUXILIARY and item and hasattr(item, 'auxiliary_data'):
            self.auxiliary = item

    def set_process(self, process: PROCESS_UNION):
        """
        Sets the process of the request.

        Args:
            process (process.PROCESS_UNION): The process.
        """
        self.process = process

    def get_process(self) -> PROCESS_UNION:
        """
        Returns the process or the capability process of the request

        Returns:
            process.PROCESS_UNION: The process.
        """
        return self.process

    def get_product(self) -> Product:
        """
        Returns the product of the request.

        Returns:
            product.Product: The product.
        """
        return self.product

    def get_resource(self) -> Resource:
        """
        Returns the resource of the request.

        Returns:
            resources.Resource: The resource.
        """
        return self.resource

    def copy_cached_routes(self, cached_request: Request) -> None:
        """
        Copies routes from a cached request.
        
        Args:
            cached_request (TransportResquest): The cached request with routes.
        """
        if hasattr(cached_request, 'route') and hasattr(self, 'route'):
            self.route = cached_request.route

    def set_route(self, route: List[Locatable]) -> None:
        """
        Sets the route for a transport request.
        
        Args:
            route (List[Locatable]): The route as a list of locations.
        """
        if hasattr(self, 'route'):
            self.route = route

    def get_route(self) -> List[Locatable]:
        """
        Returns the route of the request.

        Returns:
            List[Locatable]: The route as a list of locations.
        """
        if hasattr(self, 'route'):
            return self.route
        return []

    def get_origin(self) -> Locatable:
        """
        Returns the origin of the request.

        Returns:
            Locatable: The origin location.
        """
        return self.origin

    def get_target(self) -> Locatable:
        """
        Returns the target of the request.

        Returns:
            Locatable: The target location.
        """
        return self.target

    def get_auxiliaries(self) -> List[Auxiliary]:
        """
        Returns the auxiliaries of the request.

        Returns:
            List[Auxiliary]: The list of auxiliaries.
        """
        if hasattr(self, 'auxiliary'):
            return [self.auxiliary]
        return []
