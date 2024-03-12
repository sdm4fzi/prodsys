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


from prodsys.simulation import (
    request,
    process,
    #router,
    #resources,
    #router,
    sim,
    state,
    #sink,
    #source,
    #product
)
from prodsys.models import auxiliary_data, queue_data

class Auxiliary(BaseModel):
    """
    Class that represents a product in the discrete event simulation. For easier instantion of the class, use the ProductFactory at prodsys.factories.product_factory.

    Args:
        env (sim.Environment): prodsys simulation environment.
        auxilary_data (auxilary.Auxilary): Auxilary data of the product.
    """

    env: sim.Environment
    auxiliary_data: auxiliary_data.AuxiliaryData
    transport_process: process.Process
    storage: queue_data.StorageData
    
    
    auxiliary_router: Optional[router.Router] = Field(default=None, init=False)
    current_location: Union[product.Location, queue_data.StorageData] = Field(default=None, init=False)
    current_product: product.Product = Field(default=None, init=False)
    requested: events.Event = Field(default=None, init=False)
    ready_to_use: events.Event = Field(default=None, init=False)

    class Config:
        arbitrary_types_allowed = True
    
    def start_auxiliary(self):
        auxiliary = self.auxiliary_factory.create_auxiliary(
            self.auxiliary_data, self.storage, 
        )
        self.env.process()
            

    def request(self, process_request: request.TransportResquest) -> None:
        """
        Request the auxiliary component to be transported to a Location of a product.

        Args:
            process_request (request.Request): The request to be processed.
        """
        self.current_product = process_request.product
        logger.debug({"ID": self.auxiliary_data.ID, "sim_time": self.env.now, "resource": process_request.resource.data.ID, "event": f"Got requested by {process_request.product.auxiliary_data.ID}"})
        if not self.requested.triggered:
            logger.debug({"ID": self.auxiliary_data.ID, "sim_time": self.env.now, "resource": process_request.resource.data.ID, "event": "Triggered requested event"})
            self.requested.succeed()

    def update_location(self, location: product.Location):
        """
        Updates the location of the product object.

        Args:
            resource (Location): Location of the product object.
        """
        self.current_location = location
        logger.debug({"ID": self.auxiliary_data.ID, "sim_time": self.env.now, "resource": self.current_location.data.ID, "event": f"Updated location to {self.current_location.data.ID}"})

    def process_auxiliary(self, transport_request: request.TransportResquest):
        self.finished_process = events.Event(self.env)
        logger.debug({"ID": self.auxiliary_data.ID, "sim_time": self.env.now, "event": f"Start processing of auxiliary component"})
        while True:
            yield self.requested # why is it jumping out here?
            if self.requested.triggered:
                self.requested = events.Event(self.env)
            yield self.env.process(self.request_process(transport_request))
            yield self.finished_process
            # 5. update location of auxiliary to product location, trigger ready_to_use event to conitnue processing of the product
            self.ready_to_use.succeed()
            # 6. yield until product is finished processing (maybe use also a release event....) -> remove auxiliary from product
            
            # 7. update the location of the auxiliary
            # 8. request transport to storage location
        # important to check:
        # - if transported, auxiliaries should'nt be placed in queues, like with products -> change logic in controllers to make case distinction.
        # - transport of auxiliaries (when not attached to products) should be logged similarly as products -> check if this is the case
    

    def request_process(self, processing_request: request.Request) -> Generator:
        """
        Requests the next production process of the product object from the next production resource by creating a request event and registering it at the environment.
        """
        if isinstance(processing_request, request.TransportResquest):
            type_ = state.StateTypeEnum.transport
        else:
            type_ = state.StateTypeEnum.production
        logger.debug({"ID": self.auxiliary_data.ID, "sim_time": self.env.now, "resource": processing_request.resource.data.ID, "event": f"Request process {processing_request.process.process_data.ID} for {type_}"})
        self.env.request_process_of_resource(
            request=processing_request
        )
        yield self.finished_process
        logger.debug({"ID": self.auxiliary_data.ID, "sim_time": self.env.now, "resource": processing_request.resource.data.ID, "event": f"Finished process {processing_request.process.process_data.ID} for {type_}"})
        #TODO: Check here how i can do the logging
        self.product_info.log_end_process(
            resource=processing_request.resource,
            _product=self,
            event_time=self.env.now,
            state_type=type_,
        )
        self.finished_process = events.Event(self.env)
#from prodsys.simulation import product
#Auxiliary.update_forward_refs()