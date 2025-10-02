from __future__ import annotations

from typing import Union, Optional, TYPE_CHECKING


import logging

from prodsys.simulation.dependency import DependencyInfo


logger = logging.getLogger(__name__)

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


from prodsys.models import primitives_data

class Primitive:
    """
    Class that represents an auxiliary in the discrete event simulation. For easier instantion of the class, use the AuxiliaryFactory at prodsys.factories.auxiliary_factory.
    """

    def __init__(
        self,
        env: sim.Environment,
        data: primitives_data.PrimitiveData,
        transport_process: process.Process,
        storage: Union[port.Store, port.Queue, port.Queue_per_product],
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
        self.current_locatable: Optional[product.Locatable] = None
        self.current_dependant: Union[product.Product, Resource] = None
        self.bound = False
        self.got_free = events.Event(self.env)
        self.finished_process = events.Event(self.env)
        # self.primitive_info = PrimitiveInfo()
        self.dependency_info = DependencyInfo(primitive_id=self.data.ID)

    def update_location(self, locatable: product.Locatable):
        """
        Updates the location of the product object.

        Args:
            locatable (Locatable): Location of the product object.
        """
        self.current_locatable = locatable
        logger.debug(
            {
                "ID": self.data.ID,
                "sim_time": self.env.now,
                "resource": self.current_locatable.data.ID,
                "event": f"Updated location to {self.current_locatable.data.ID}",
            }
        )

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


from prodsys.simulation import port, product, state
