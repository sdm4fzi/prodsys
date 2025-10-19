from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Optional, List, Union

import simpy

from prodsys.simulation.entities.entity import EntityType

if TYPE_CHECKING:
    from prodsys.simulation.locatable import Locatable
    from prodsys.simulation.process import (
        PROCESS_UNION,
    )
    # from prodsys.simulation.primitive import Primitive
    from prodsys.simulation.entities.product import Product
    from prodsys.simulation.entities.primitive import Primitive
    from prodsys.simulation.entities.lot import Lot

    from prodsys.simulation.resources import Resource
    from prodsys.simulation.port import Store, Queue
    from prodsys.simulation.dependency import DependedEntity
    from prodsys.simulation.process import Process
    from prodsys.simulation.dependency import Dependency


class RequestType(str, Enum):
    """
    Enum to represent the type of request.

    Attributes:
        TRANSPORT: Represents a transport request.
        MOVE: Represents a move request.
        REWORK: Represents a rework request.
        PRODUCTION: Represents a production request.
        PRIMITIVE_DEPENDENCY: Represents a primitive dependency request.
        PROCESS_DEPENDENCY: Represents a process dependency request.
        RESOURCE_DEPENDENCY: Represents a resource dependency request.
        PROCESS_MODEL: Represents a process model request.
    """

    TRANSPORT = "transport"
    MOVE = "move"
    REWORK = "rework"
    PRODUCTION = "production"
    PRIMITIVE_DEPENDENCY = "primitive"
    PROCESS_DEPENDENCY = "process_dependency"
    RESOURCE_DEPENDENCY = "resource_dependency"
    PROCESS_MODEL = "process_model"


class Request:
    """
    Class to represents requests of a product for a process to be executed by a resource.

    Args:
        request_type (RequestType): Type of the request.
        process (process.PROCESS_UNION): The process that is requested.
        resource (Optional[Resource]): The resource that is requested.
        requesting_item (Optional[Product | Primitive]): The item that is requested.
        item (Optional[Product | Primitive]): The item that is requested.
        origin_queue (Optional[Queue]): The origin queue.
        target_queue (Optional[Store]): The target queue.
        origin (Optional[Locatable]): The origin location for transport.
        target (Optional[Locatable]): The target location for transport.
    """

    def __init__(
        self,
        request_type: RequestType,
        process: PROCESS_UNION,
        resource: Optional[Resource] = None,
        requesting_item: Optional[Product | Primitive | Lot | Resource | Process] = None,
        entity: Optional[Product | Primitive | Lot] = None,
        origin_queue: Optional[Queue] = None,
        target_queue: Optional[Store] = None,
        origin: Optional[Locatable] = None,
        target: Optional[Locatable] = None,
        completed: Optional[simpy.Event] = None,
        route: Optional[List[Locatable]] = None,
        resolved_dependency: Optional[Dependency] = None,
        required_dependencies: Optional[list[Dependency]] = None,
        dependency_release_event: Optional[simpy.Event] = None,
    ):
        self.request_type = request_type
        self.process = process
        self.requesting_item = requesting_item
        self.entity = entity
        self.resource = resource
        self.origin = origin
        self.target = target
        self.origin_queue: Optional[Queue] = origin_queue
        self.target_queue: Optional[Store] = target_queue
        self.completed = completed

        self.transport_to_target: Optional[simpy.Event] = None

        self.resolved_dependency: Optional[Dependency] = resolved_dependency
        self.required_dependencies: Optional[List[Dependency]] = (
            required_dependencies
        )
        self.dependencies_requested: Optional[simpy.Event] = simpy.Event(
            self.requesting_item.env
        )
        self.dependencies_ready: Optional[simpy.Event] = simpy.Event(
            self.requesting_item.env
        )
        self.lot_process_time: Optional[float] = None

        self.requesting_item = requesting_item
        self.route: Optional[List[Locatable]] = route
        self.dependency_release_event: Optional[simpy.Event] = dependency_release_event

    
    @property
    def capacity_required(self) -> int:
        """
        Returns the capacity required for the request.
        For dependency requests (PROCESS_DEPENDENCY, RESOURCE_DEPENDENCY), returns 1.
        For entity-based requests (PRODUCTION, TRANSPORT, etc.), returns the entity size.
        """
        # Dependency requests don't need entity size, they always require capacity of 1 but block the resource completely until finished.
        if self.request_type in (RequestType.PROCESS_DEPENDENCY, RequestType.RESOURCE_DEPENDENCY):
            return 1
        return self.entity.size
    
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

    def get_entity(self) -> Union[Product, Primitive, Lot]:
        """
        Returns the item of the request.

        Returns:
            Union[product.Product, primitive.Primitive]: The item (product or primitive).
        """
        return self.entity

    def get_atomic_entities(self) -> List[Union[Product, Primitive]]:
        if self.entity.type == EntityType.PRODUCT:
            return [self.entity]
        elif self.entity.type == EntityType.PRIMITIVE:
            return [self.entity]
        elif self.entity.type == EntityType.LOT:
            return self.entity.get_atomic_entities()
        else:
            raise ValueError(f"Entity type {self.entity.type} not supported.")

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
        if hasattr(cached_request, "route") and hasattr(self, "route"):
            self.route = cached_request.route

    def set_route(self, route: List[Locatable]) -> None:
        """
        Sets the route for a transport request.

        Args:
            route (List[Locatable]): The route as a list of locations.
        """
        if hasattr(self, "route"):
            self.route = route

    def get_route(self) -> List[Locatable]:
        """
        Returns the route of the request.

        Returns:
            List[Locatable]: The route as a list of locations.
        """
        if hasattr(self, "route"):
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

    def request_dependencies(self) -> simpy.Event:
        """
        Requests the dependencies of the request.
        """
        self.dependencies_requested.succeed()
        return self.dependencies_ready

    def bind_dependencies(self, dependencies: List[DependedEntity]) -> None:
        """
        Binds the dependencies to the request.

        Args:
            dependencies (List[DependedEntity]): The list of dependencies to bind.
        """
        self.required_dependencies = dependencies
        for dependency in self.required_dependencies:
            dependency.bind(self)