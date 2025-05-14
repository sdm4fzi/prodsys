from __future__ import annotations

from typing import Union, Optional, TYPE_CHECKING


import logging


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
        store,
        state,
    )
    from prodsys.simulation import router as router_module


from prodsys.models import primitives_data


class PrimitiveInfo:
    """
    Class that represents information of the current state of a product.

    Args:
        resource_ID (str): ID of the resource that the product is currently at.
        state_ID (str): ID of the state that the product is currently at.
        event_time (float): Time of the event.
        activity (state.StateEnum): Activity of the product.
        product_ID (str): ID of the product.
        state_type (state.StateTypeEnum): Type of the state.
    """

    def __init__(self):
        """
        Initializes the AuxiliaryInfo class.
        """
        self.resource_ID: str = None
        self.state_ID: str = None
        self.event_time: float = None
        self.activity: state.StateEnum = None
        self.product_ID: str = None
        self.state_type: state.StateTypeEnum = None

    def log_create_primitive(
        self,
        resource: Union[resources.Resource, sink.Sink, source.Source, store.Store],
        _product: Primitive,
        event_time: float,
    ) -> None:
        """
        Logs the creation of an auxiliary.

        Args:
            resource (Union[resources.Resource, sink.Sink, source.Source]): New resource of the auxiliary.
            _product (Product): Product that is created.
            event_time (float): Time of the event.
        """
        self.resource_ID = resource.data.ID
        self.state_ID = resource.data.ID
        self.event_time = event_time
        self.product_ID = _product.data.ID
        self.activity = state.StateEnum.created_auxiliary
        self.state_type = state.StateTypeEnum.store

    def log_bind(
        self,
        resource: resources.Resource,
        _product: Primitive,
        event_time: float,
    ) -> None:
        """
        Logs the start of the usage of an auxiliary.

        Args:

            resource (resources.Resource): Resource that the product is processed at.
            _product (Product): Product that is processed.
            event_time (float): Time of the event.
            state_type (state.StateTypeEnum): Type of the state.
        """
        self.resource_ID = resource.data.ID
        self.state_ID = resource.data.ID
        self.event_time = event_time
        self.product_ID = _product.data.ID
        self.activity = state.StateEnum.started_auxiliary_usage
        self.state_type = state.StateTypeEnum.production

    def log_release(
        self,
        resource: resources.Resource,
        _product: Primitive,
        event_time: float,
    ) -> None:
        """
        Logs the end of the usage of an auxiliary.

        Args:
            resource (resources.Resource): Resource that the product is processed at.
            _product (Product): Product that is processed.
            event_time (float): Time of the event.
        """
        self.resource_ID = resource.data.ID
        self.state_ID = resource.data.ID
        self.event_time = event_time
        self.product_ID = _product.data.ID
        self.activity = state.StateEnum.finished_auxiliary_usage
        self.state_type = state.StateTypeEnum.production


class Primitive:
    """
    Class that represents an auxiliary in the discrete event simulation. For easier instantion of the class, use the AuxiliaryFactory at prodsys.factories.auxiliary_factory.
    """

    def __init__(
        self,
        env: sim.Environment,
        primitive_data: primitives_data.PrimitiveData,
        transport_process: process.Process,
        storage: store.Store,
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
        self.data = primitive_data
        self.transport_process = transport_process
        self.storage = storage

        self.router: router_module.Router = None
        self.current_locatable: Optional[product.Locatable] = None
        self.current_dependant: Union[product.Product, Resource] = None
        self.bound = False
        self.got_free = events.Event(self.env)
        self.finished_process = events.Event(self.env)
        self.primitive_info = PrimitiveInfo()

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

    def bind(self, dependant: Union[product.Product, resources.Resource]) -> None:
        """
        Reserves the product object.
        """
        if self.bound:
            raise Exception(
                f"Primitive {self.data.ID} is bound reserved. Cannot bind again."
            )
        self.bound = True
        self.current_dependant = dependant
        self.primitive_info.log_bind(
            resource=self.current_locatable,
            _product=self,
            event_time=self.env.now,
            # TODO: add dependant to log
        )

    def release(self):
        """
        Releases the auxiliary from the product after storage of the auxiliary.
        """
        self.current_dependant = None
        self.bound = False
        self.got_free.succeed()
        self.got_free = events.Event(self.env)
        self.primitive_info.log_release(
            resource=self.current_locatable,
            _product=self,
            event_time=self.env.now,
        )

from prodsys.simulation import product
