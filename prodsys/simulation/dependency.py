from __future__ import annotations

from typing import Optional, Protocol, TYPE_CHECKING, runtime_checkable

import logging



from prodsys.simulation.entities import primitive
from prodsys.simulation import state
if TYPE_CHECKING:
    from prodsys.simulation import resources

    from prodsys.models import dependency_data
    from prodsys.simulation import (
        process,
        sim,
        state,
        node,
    )

logger = logging.getLogger(__name__)

class DependedEntity(Protocol):
    """
    Protocol that defines the interface for a depended entity. This is used to define the type of the depended entity in the Dependency class.
    """

    def bind(self, dependant: process.Process | resources.Resource | primitive.Primitive, dependency: Dependency) -> None:
        """
        Binds the depended entity to the dependency.
        """
        pass
        # When binding the items, they should be transport to the location of destination
        # they should go in a status so that they are not used elsewhere, until release is called.

    def release(self):
        """
        Releases the product object.
        """
        pass
        # release should make DependedEntity available for other processes
        # called by the dependant


class DependencyInfo:
    """
    Class that represents information of the current state of a resource.

    Args:
        resource_ID (str): ID of the resource that the product is currently at.
        state_ID (str): ID of the state that the product is currently at.
        event_time (float): Time of the event.
        activity (state.StateEnum): Activity of the product.
        product_ID (str): ID of the product.
        state_type (state.StateTypeEnum): Type of the state.
    """

    def __init__(self, resource_id: Optional[str]=None, primitive_id: Optional[str]=None):
        """
        Initializes the DependencyInfo class.
        """
        self.resource_ID: str = resource_id
        self.state_ID: str = "Dependency"
        self.event_time: float = None
        self.activity: state.StateEnum = None
        self.primitive_ID: str = primitive_id
        self.state_type: state.StateTypeEnum = state.StateTypeEnum.dependency
        # self.state_type: state.StateTypeEnum = state.StateTypeEnum.production
        self.requesting_item_ID: str = None
        self.dependency_ID: str = None

    def log_start_dependency(
        self,
        event_time: float,
        requesting_item_id: str,
        dependency_id: str,
    ) -> None:
        """
        Logs the start of a dependency.

        Args:
            event_time (float): Time of the event.
            activity (state.StateEnum): Activity of the product.
            requesting_item (str): ID of the product that is requesting the dependency.
        """
        self.event_time = event_time
        self.activity = state.StateEnum.start_state
        self.requesting_item_ID = requesting_item_id
        self.dependency_ID = dependency_id

    def log_end_dependency(
        self,
        event_time: float,
        requesting_item_id: str,
        dependency_id: str,
    ) -> None:
        """
        Logs the end of a dependency.

        Args:
            event_time (float): Time of the event.
            activity (state.StateEnum): Activity of the product.
            requesting_item (str): ID of the product that is requesting the dependency.
        """
        self.event_time = event_time
        self.activity = state.StateEnum.end_state
        self.requesting_item_ID = requesting_item_id
        self.dependency_ID = dependency_id


class Dependency:
    """
    Class that represents a dependency in the discrete event simulation. For easier instantion of the class, use the PrimitiveFactory at prodsys.factories.primitive.
    """

    def __init__(
        self,
        env: sim.Environment,
        data: dependency_data.DependencyData,
        required_process: Optional[process.Process],
        required_entity: Optional[primitive.Primitive],
        required_resource: Optional[resources.Resource],
        interaction_node: Optional[node.Node],
    ):
        """
        Initializes the Dependency class.

        Args:
            env (sim.Environment): prodsys simulation environment.
            data (dependency_data.DependencyData): Dependency data of the product.
            required_process (process.Process): Required process of the product.
            required_primitive (primitive.Primitive): Required primitive of the product.
            required_resource (resources.Resource): Required resource of the product.
            interaction_node (node.Node): Interaction node of the product.
        """
        self.env = env
        self.data = data
        self.required_process = required_process
        self.required_entity = required_entity
        self.required_resource = required_resource
        self.interaction_node = interaction_node


