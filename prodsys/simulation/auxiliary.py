from __future__ import annotations

from abc import ABC
from enum import Enum
from collections.abc import Iterable
from typing import List, Union, Optional, TYPE_CHECKING, Generator

from pydantic import BaseModel, Field, Extra

import logging
logger = logging.getLogger(__name__)

from simpy import events

from pydantic import BaseModel

if TYPE_CHECKING:
    from prodsys.simulation import router, product, resources, sink, source
    from prodsys.factories import auxiliary_factory


from prodsys.simulation import (
    request,
    process,
    #router,
    #resources,
    #router,
    sim,
    state,
    store,
    #sink,
    #source,
    #product
)
from prodsys.models import auxiliary_data, queue_data

class AuxiliaryInfo(BaseModel, extra=Extra.allow):
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

    def log_create_auxiliary(
        self,
        resource: Union[resources.Resource, sink.Sink, source.Source, store.Storage],
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
    Class that represents a product in the discrete event simulation. For easier instantion of the class, use the ProductFactory at prodsys.factories.product_factory.

    Args:
        env (sim.Environment): prodsys simulation environment.
        auxilary_data (auxilary.Auxilary): Auxilary data of the product.
    """

    env: sim.Environment
    data: auxiliary_data.AuxiliaryData
    transport_process: process.Process
    storage: store.Storage

    
    auxiliary_router: Optional[router.Router] = Field(default=None, init=False)
    current_location: Union[product.Location, store.Storage] = Field(default=None, init=False)
    current_product: product.Product = Field(default=None, init=False)
    finished_auxiliary_process: events.Event = Field(default=None, init=False)
    got_free: events.Event = Field(default=None, init=False)
    auxiliary_info: AuxiliaryInfo = AuxiliaryInfo()


    class Config:
        arbitrary_types_allowed = True
            

    # def request(self) -> None:
    #     """
    #     Request the auxiliary component to be transported to a Location of a product.

    #     Args:
    #         process_request (request.Request): The request to be processed.
    #     """
    #     #allocate the product to the auxiliary
    #     self.current_product = process_request.product
    #     # if not self.requested.triggered:
    #     #     self.requested.succeed()
    #     #     print(self.requested)

    def update_location(self, location: product.Location):
        """
        Updates the location of the product object.

        Args:
            resource (Location): Location of the product object.
        """
        self.current_location = location
        logger.debug({"ID": self.data.ID, "sim_time": self.env.now, "resource": self.current_location.data.ID, "event": f"Updated location to {self.current_location.data.ID}"})

    def get_auxiliary(self, transport_request: request.TransportResquest):
        self.finished_auxiliary_process = events.Event(self.env)
        self.got_free = events.Event(self.env)
        yield self.env.process(self.auxiliary_router.route_request(transport_request))
        yield self.env.process(self.request_process(transport_request))

    def release_auxiliary(self) -> Generator:
        self.finished_auxiliary_process = events.Event(self.env)
        storage_transport_request = request.TransportResquest(
                    process = self.transport_process,
                    product = self, 
                    origin = self.current_location,
                    target = self.storage
                )
        yield self.env.process(self.auxiliary_router.route_request(storage_transport_request))
        yield self.env.process(self.request_process(storage_transport_request))
        self.current_product = None
        if not self.got_free.triggered:
            self.got_free.succeed()
        self.got_free = events.Event(self.env)
        self.update_location(self.storage)
        yield self.env.timeout(0)

    def request_process(self, processing_request: request.Request) -> Generator:
        """
        Requests the next production process of the product object from the next production resource by creating a request event and registering it at the environment.
        """
        if isinstance(processing_request, request.TransportResquest):
            type_ = state.StateTypeEnum.transport
        else:
            type_ = state.StateTypeEnum.production
        logger.debug({"ID": self.data.ID, "sim_time": self.env.now, "resource": processing_request.resource.data.ID, "event": f"Request process {processing_request.process.process_data.ID} for {type_}"})
        self.env.request_process_of_resource(
            request=processing_request
        )
        yield self.finished_auxiliary_process
        logger.debug({"ID": self.data.ID, "sim_time": self.env.now, "resource": processing_request.resource.data.ID, "event": f"Finished process {processing_request.process.process_data.ID} for {type_}"})
        self.auxiliary_info.log_end_process(
            resource=processing_request.resource,
            _product=self,
            event_time=self.env.now,
            state_type=type_,
        )
        self.finished_auxiliary_process = events.Event(self.env)

# from prodsys.simulation import product
# Auxiliary.update_forward_refs()