from __future__ import annotations

from typing import Optional, Protocol, TYPE_CHECKING

import logging

logger = logging.getLogger(__name__)


from prodsys.simulation import primitive

if TYPE_CHECKING:
    from prodsys.simulation import product, resources, sink, source
    from prodsys.factories import primitive_factory

    from prodsys.models import dependency_data
    from prodsys.simulation import (
        request,
        process,
        sim,
        store,
        state,
    )

class DependedEntity(Protocol):
    """
    Protocol that defines the interface for a depended entity. This is used to define the type of the depended entity in the Dependency class.
    """
    def bind(self, dependant: process.Process | resources.Resource | primitive.Primitive) -> None:
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

    # TODO: use these function and consider them for state / product_info logging, also add logging to primitives


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
        Initializes the AuxiliaryInfo class.
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
    Class that represents an auxiliary in the discrete event simulation. For easier instantion of the class, use the AuxiliaryFactory at prodsys.factories.auxiliary_factory.

    Args:
        env (sim.Environment): prodsys simulation environment.
        auxilary_data (auxilary.Auxilary): Auxilary data of the product.
    """

    env: sim.Environment
    data: dependency_data.DependencyData
    required_process: process.Process
    required_primitive: primitive.Primitive
    required_resource: resources.Resource

    def __init__(
        self,
        env: sim.Environment,
        data: dependency_data.DependencyData,
        required_process: process.Process,
        required_primitive: primitive.Primitive,
        required_resource: resources.Resource,
    ):
        """
        Initializes the Auxiliary class.

        Args:
            env (sim.Environment): prodsys simulation environment.
            auxilary_data (auxilary.Auxilary): Auxilary data of the product.
            transport_process (process.Process): Transport process of the product.
            storage (store.Store): Storage of the product.
            relevant_processes (List[Union[process.ProductionProcess, process.CapabilityProcess]]): Relevant processes of the product.
            relevant_transport_processes (List[process.TransportProcess]): Relevant transport processes of the product.
        """
        self.env = env
        self.data = data
        self.required_process = required_process
        self.required_primitive = required_primitive
        self.required_resource = required_resource


from prodsys.simulation import state