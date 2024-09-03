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

if TYPE_CHECKING:
    from prodsys.simulation import router, product, resources, sink, source
    from prodsys.factories import auxiliary_factory

from prodsys.models import auxiliary_data
from prodsys.simulation import (
    request,
    process,
    sim,
    store,
    state,
)

class AuxiliaryInfo(BaseModel):
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

    resource_ID: str = Field(init=False, default=None)
    state_ID: str = Field(init=False, default=None)
    event_time: float = Field(init=False, default=None)
    activity: state.StateEnum = Field(init=False, default=None)
    product_ID: str = Field(init=False, default=None)
    state_type: state.StateTypeEnum = Field(init=False, default=None)   

    model_config=ConfigDict(extra="allow")         

    def log_create_auxiliary(
        self,
        resource: Union[resources.Resource, sink.Sink, source.Source, store.Queue],
        _product: Auxiliary,
        event_time: float,
    ) -> None:
        """
        Logs the creation of an auxiliary.

        Args:
            resource (Union[resources.Resource, sink.Sink, source.Source]): New resource of the product.
            _product (Product): Product that is created.
            event_time (float): Time of the event.
        """
        self.resource_ID = resource.data.ID
        self.state_ID = resource.data.ID
        self.event_time = event_time
        self.product_ID = _product.data.ID
        self.activity = state.StateEnum.created_auxiliary        
        self.state_type = state.StateTypeEnum.store

    def log_start_process(
        self,
        resource: resources.Resource,
        _product: Auxiliary,
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
        _product: Auxiliary,
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

class Auxiliary(BaseModel):
    """
    Class that represents an auxiliary in the discrete event simulation. For easier instantion of the class, use the AuxiliaryFactory at prodsys.factories.auxiliary_factory.

    Args:
        env (sim.Environment): prodsys simulation environment.
        auxilary_data (auxilary.Auxilary): Auxilary data of the product.
    """

    env: sim.Environment
    data: auxiliary_data.AuxiliaryData
    transport_process: process.Process
    storage: store.Queue

    
    auxiliary_router: Optional[router.Router] = Field(default=None, init=False)
    current_locatable: Union[product.Locatable, store.Queue] = Field(default=None, init=False)
    current_product: product.Product = Field(default=None, init=False)
    reserved: bool = Field(default=False, init=False)
    got_free: events.Event = Field(default=None, init=False)
    finished_process: events.Event = Field(default=None, init=False)
    auxiliary_info: AuxiliaryInfo = AuxiliaryInfo()


    class Config:
        arbitrary_types_allowed = True

    def init_got_free(self):
        """
        Sets the got_free event.

        Args:
            event (events.Event): The event to set.
        """
        self.got_free = events.Event(self.env)
        self.reserved = False
        self.finished_process = events.Event(self.env)

    @property
    def product_data(self):
        return self.data

    def update_location(self, locatable: product.Locatable):
        """
        Updates the location of the product object.

        Args:
            locatable (Locatable): Location of the product object.
        """
        self.current_locatable = locatable
        logger.debug({"ID": self.data.ID, "sim_time": self.env.now, "resource": self.current_locatable.data.ID, "event": f"Updated location to {self.current_locatable.data.ID}"})

    def reserve(self):
        """
        Reserves the product object.
        """
        self.reserved = True
        self.got_free = events.Event(self.env)
    
    def release_auxiliary_from_product(self):
        """
        Releases the auxiliary from the product after storage of the auxiliary.
        """
        print("release auxiliary from product", self.data.ID)
        self.current_product = None
        self.got_free.succeed()
        self.reserved = False
        yield self.env.timeout(0)


    def request_process(self, processing_request: request.TransportResquest) -> Generator:
        """
        Requests the next production process of the product object from the next production resource by creating a request event and registering it at the environment.
        """
        self.finished_process = events.Event(self.env)

        type_ = state.StateTypeEnum.transport
        logger.debug({"ID": self.product_data.ID, "sim_time": self.env.now, "resource": processing_request.resource.data.ID, "event": f"Request process {processing_request.process.process_data.ID} for {type_}"})
        self.env.request_process_of_resource(
            request=processing_request
        )
        print("start waitining for auxiliary get", self.data.ID)
        yield self.finished_process
        logger.debug({"ID": self.product_data.ID, "sim_time": self.env.now, "resource": processing_request.resource.data.ID, "event": f"Finished process {processing_request.process.process_data.ID} for {type_}"})
        self.auxiliary_info.log_end_process(
            resource=processing_request.resource,
            _product=self,
            event_time=self.env.now,
            state_type=type_,
        )
        print("finished auxiliary get", self.data.ID, self.current_locatable.data.ID)

from prodsys.simulation import product
# Auxiliary.update_forward_refs()
