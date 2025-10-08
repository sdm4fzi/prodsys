from __future__ import annotations

from typing import Union, Optional, TYPE_CHECKING


import logging

from prodsys.simulation.entities.entity import Entity, EntityType
from prodsys.simulation.dependency import DependencyInfo



from simpy import events


if TYPE_CHECKING:
    from prodsys.simulation import product, resources, sink, source
    from prodsys.factories import primitive_factory
    from prodsys.simulation.resources import Resource
    from prodsys.simulation import (
        request,
        process,
        sim,
        state,
    )
    from prodsys.simulation import router as router_module
    from prodsys.simulation.dependency import Dependency
    from prodsys.simulation import locatable


from prodsys.models import primitives_data

logger = logging.getLogger(__name__)


class Primitive(Entity):
    """
    Class that represents an auxiliary in the discrete event simulation. For easier instantion of the class, use the AuxiliaryFactory at prodsys.factories.auxiliary_factory.
    """

    def __init__(
        self,
        env: sim.Environment,
        data: primitives_data.PrimitiveData,
        transport_process: process.Process,
        storage: port.Store,
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
        self.transport_process = transport_process
        self.storage = storage

        self.router: router_module.Router = None
        self.current_locatable: Optional[locatable.Locatable] = None
        self.current_dependant: Union[product.Product, Resource] = None
        self.bound = False
        self.got_free = events.Event(self.env)
        self.finished_process = events.Event(self.env)
        # self.primitive_info = PrimitiveInfo()
        self.dependency_info = DependencyInfo(primitive_id=self.data.ID)

    
    @property
    def type(self) -> EntityType:
        return EntityType.PRIMITIVE

    @property
    def size(self) -> int:
        return 1

    def update_location(self, locatable: locatable.Locatable):
        """
        Updates the location of the product object.

        Args:
            locatable (Locatable): Location of the product object.
        """
        self.current_locatable = locatable

    def bind(self, dependant: Union[product.Product, resources.Resource], dependency: Dependency) -> None:
        """
        Reserves the product object.
        """
        if self.bound:
            raise Exception(
                f"Primitive {self.data.ID} is bound reserved. Cannot bind again."
            )
        self.bound = True
        self.current_dependant = dependant
        dependant.depended_entities.append(self)
        self.dependency_info.log_start_dependency(
            event_time=self.env.now,
            requesting_item_id=dependant.data.ID if dependant else None,
            dependency_id=dependency.data.ID,
        )

    def release(self):
        """
        Releases the auxiliary from the product after storage of the auxiliary.
        """
        self.dependency_info.log_end_dependency(
            event_time=self.env.now,
            requesting_item_id=self.current_dependant.data.ID if self.current_dependant else None,
            dependency_id=self.data.ID,
        )
        self.current_dependant = None
        self.bound = False
        self.got_free.succeed()
        self.got_free = events.Event(self.env)


from prodsys.simulation import port
from prodsys.simulation.entities import product
