from __future__ import annotations

from abc import ABC
from enum import Enum
from collections.abc import Iterable
from typing import List, Union, Optional, TYPE_CHECKING, Generator

from pydantic import BaseModel, ConfigDict, Field

import logging

logger = logging.getLogger(__name__)

from simpy import events

from pydantic import BaseModel
from prodsys.simulation import router as router_module

if TYPE_CHECKING:
    from prodsys.simulation import product, resources, sink, source
    from prodsys.factories import auxiliary_factory

from prodsys.models import dependency_data, primitives_data
from prodsys.simulation import (
    request,
    process,
    sim,
    store,
    state,
)


class AuxiliaryInfo:
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

    def log_create_auxiliary(
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

    def log_start_auxiliary_usage(
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

    def log_end_auxiliary_usage(
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

    def log_start_process(
        self,
        resource: resources.Resource,
        _product: Primitive,
        event_time: float,
        state_type: state.StateTypeEnum,
    ) -> None:
        """
        Logs the start of a process.

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
        self.activity = state.StateEnum.start_state
        self.state_type = state_type

    def log_end_process(
        self,
        resource: resources.Resource,
        _product: Primitive,
        event_time: float,
        state_type: state.StateTypeEnum,
    ) -> None:
        """
        Logs the end of a process.

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
        self.activity = state.StateEnum.end_state
        self.state_type = state_type


class Primitive:
    """
    Class that represents an auxiliary in the discrete event simulation. For easier instantion of the class, use the AuxiliaryFactory at prodsys.factories.auxiliary_factory.

    Args:
        env (sim.Environment): prodsys simulation environment.
        auxilary_data (auxilary.Auxilary): Auxilary data of the product.
    """

    env: sim.Environment
    data: primitives_data.PrimitiveData
    transport_process: process.Process
    storage: store.Store

    primitive_router: Optional[router_module.Router] = Field(default=None, init=False)
    current_locatable: Union[product.Locatable, store.Store] = Field(
        default=None, init=False
    )
    current_dependant: product.Product = Field(default=None, init=False)
    reserved: bool = Field(default=False, init=False)
    got_free: events.Event = Field(default=None, init=False)
    finished_process: events.Event = Field(default=None, init=False)
    auxiliary_info: AuxiliaryInfo = AuxiliaryInfo()

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(
        self,
        env: sim.Environment,
        auxilary_data: dependency_data.AuxiliaryData,
        transport_process: process.Process,
        storage: store.Store,
        relevant_processes: List[
            Union[process.ProductionProcess, process.CapabilityProcess]
        ],
        relevant_transport_processes: List[process.TransportProcess],
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
        self.data = auxilary_data
        self.transport_process = transport_process
        self.storage = storage
        self.relevant_processes = relevant_processes
        self.relevant_transport_processes = relevant_transport_processes

        self.primitive_router = None
        self.current_locatable = None
        self.current_dependant = None
        self.reserved = False
        self.got_free = events.Event(self.env)
        self.finished_process = events.Event(self.env)
        self.auxiliary_info = AuxiliaryInfo()

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

    def reserve(self):
        """
        Reserves the product object.
        """
        self.reserved = True
        self.got_free = events.Event(self.env)
        self.auxiliary_info.log_start_auxiliary_usage(
            resource=self.current_locatable,
            _product=self,
            event_time=self.env.now,
        )

    def release(self):
        """
        Releases the auxiliary from the product after storage of the auxiliary.
        """
        self.current_dependant = None
        self.reserved = False
        self.got_free.succeed()
        self.auxiliary_info.log_end_auxiliary_usage(
            resource=self.current_locatable,
            _product=self,
            event_time=self.env.now,
        )
        logger.debug(
            {
                "ID": self.data.ID,
                "sim_time": self.env.now,
                "resource": self.current_locatable.data.ID,
                "event": f"Released auxiliary from product",
            }
        )

    def request_process(self, processing_request: request.Request) -> Generator:
        """
        Requests the next production process of the product object from the next production resource by creating a request event and registering it at the environment.
        """
        self.finished_process = events.Event(self.env)

        type_ = state.StateTypeEnum.transport
        logger.debug(
            {
                "ID": self.data.ID,
                "sim_time": self.env.now,
                "resource": processing_request.resource.data.ID,
                "event": f"Request process {processing_request.process.data.ID} for {type_}",
            }
        )
        # FIXME: this is not working anymore!
        self.env.request_process_of_resource(request=processing_request)
        logger.debug(
            {
                "ID": self.data.ID,
                "sim_time": self.env.now,
                "resource": processing_request.resource.data.ID,
                "origin": processing_request.origin.data.ID,
                "target": processing_request.target.data.ID,
                "event": f"Start waiting for request to be finished",
            }
        )
        yield self.finished_process
        logger.debug(
            {
                "ID": self.data.ID,
                "sim_time": self.env.now,
                "resource": processing_request.resource.data.ID,
                "origin": processing_request.origin.data.ID,
                "target": processing_request.target.data.ID,
                "event": f"Finished waiting for request to be finished",
            }
        )
        self.auxiliary_info.log_end_process(
            resource=processing_request.resource,
            _product=self,
            event_time=self.env.now,
            state_type=type_,
        )


class ProcessAuxiliary(Primitive):
    """
    Class that represents that a certain process is required to perform the process this auxiliary is assigned to.

    Args:
        env (sim.Environment): prodsys simulation environment.
        auxilary_data (auxilary.Auxilary): Auxilary data of the product.
        required_process (process.ProductionProcess): Required process for the auxiliary.
    """

    env: sim.Environment
    data: dependency_data.ProcessAuxiliaryData
    required_process: process.ProductionProcess
    router: router_module.Router
    required_resource: Optional[resources.Resource] = Field(default=None, init=False)

    def reserve(self):
        """
        Reserves the product object.
        """
        self.reserved = True
        self.got_free = events.Event(self.env)
        self.finished_process = events.Event(self.env)

    def release(self):
        """
        Releases the resource from the auxiliary process after executing the process.
        """
        self.current_dependant = None
        self.reserved = False
        self.got_free.succeed()
        self.auxiliary_info.log_end_auxiliary_usage(
            resource=self.current_locatable,
            _product=self,
            event_time=self.env.now,
        )
        logger.debug(
            {
                "ID": self.data.ID,
                "sim_time": self.env.now,
                "resource": self.current_locatable.data.ID,
                "event": f"Released auxiliary from product",
            }
        )


class ResourceAuxiliary(Primitive):
    """
    Class that represents a process auxiliary in the discrete event simulation. For easier instantion of the class, use the AuxiliaryFactory at prodsys.factories.auxiliary_factory.

    Args:
        env (sim.Environment): prodsys simulation environment.
        auxilary_data (auxilary.Auxilary): Auxilary data of the product.
        required_resource (resources.Resource): Required resource for the auxiliary.
    """

    env: sim.Environment
    data: dependency_data.ResourceAuxiliaryData
    required_resource: resources.Resource
    router: router_module.Router

    def reserve(self):
        """
        Reserves the product object.
        """
        self.reserved = True
        self.got_free = events.Event(self.env)
        self.finished_process = events.Event(self.env)

    def release(self):
        """
        Releases the resource from the auxiliary process after executing the process.
        """
        self.current_dependant = None
        self.reserved = False
        self.got_free.succeed()
        self.auxiliary_info.log_end_auxiliary_usage(
            resource=self.current_locatable,
            _product=self,
            event_time=self.env.now,
        )
        logger.debug(
            {
                "ID": self.data.ID,
                "sim_time": self.env.now,
                "resource": self.current_locatable.data.ID,
                "event": f"Released auxiliary from product",
            }
        )


from prodsys.simulation import product
