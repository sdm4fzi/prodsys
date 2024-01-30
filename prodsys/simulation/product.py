from __future__ import annotations

from abc import ABC
from enum import Enum
from collections.abc import Iterable
from typing import List, Union, Optional, TYPE_CHECKING, Generator

from pydantic import BaseModel, Field, Extra

import logging
logger = logging.getLogger(__name__)

import numpy as np
from simpy import events

from prodsys.simulation import (
    process,
    request,
    router,
    resources,
    sim,
    sink,
    source,
    proces_models,
    state,
)

from prodsys.models import product_data


class ProductInfo(BaseModel, extra=Extra.allow):
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

    def log_finish_product(
        self,
        resource: Union[resources.Resource, sink.Sink, source.Source],
        _product: Product,
        event_time: float,
    ):
        """
        Logs the finish of a product.

        Args:
            resource (Union[resources.Resource, sink.Sink, source.Source]): New resource of the product.
            _product (Product): Product that is finished.
            event_time (float): Time of the event.
        """
        self.resource_ID = resource.data.ID
        self.state_ID = resource.data.ID
        self.event_time = event_time
        self.product_ID = _product.product_data.ID
        self.activity = state.StateEnum.finished_product
        self.state_type = state.StateTypeEnum.sink

    def log_create_product(
        self,
        resource: Union[resources.Resource, sink.Sink, source.Source],
        _product: Product,
        event_time: float,
    ) -> None:
        """
        Logs the creation of a product.

        Args:
            resource (Union[resources.Resource, sink.Sink, source.Source]): New resource of the product.
            _product (Product): Product that is created.
            event_time (float): Time of the event.
        """
        self.resource_ID = resource.data.ID
        self.state_ID = resource.data.ID
        self.event_time = event_time
        self.product_ID = _product.product_data.ID
        self.activity = state.StateEnum.created_product
        self.state_type = state.StateTypeEnum.source

    def log_start_process(
        self,
        resource: resources.Resource,
        _product: Product,
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
        self.product_ID = _product.product_data.ID
        self.activity = state.StateEnum.start_state
        self.state_type = state_type

    def log_end_process(
        self,
        resource: resources.Resource,
        _product: Product,
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
        self.product_ID = _product.product_data.ID
        self.activity = state.StateEnum.end_state
        self.state_type = state_type



class Product(BaseModel):
    """
    Class that represents a product in the discrete event simulation. For easier instantion of the class, use the ProductFactory at prodsys.factories.product_factory.

    Args:
        env (sim.Environment): prodsys simulation environment.
        product_data (product_data.ProductData): Product data that represents the meta information of the simulation product object.
        process_model (proces_models.ProcessModel): Process model that represents the required manufacturing processes and the current state of the product.
        transport_process (process.Process): Transport process that represents the required transport processes.
        product_router (router.Router): Router that is used to route the product object.
    """

    env: sim.Environment
    product_data: product_data.ProductData
    process_model: proces_models.ProcessModel
    transport_process: Union[process.LinkTransportProcess, process.TransportProcess]
    product_router: router.Router

    next_prodution_process: Optional[process.PROCESS_UNION] = Field(default=None, init=False)
    process: events.Process = Field(default=None, init=False)
    current_location: Union[resources.NodeData, resources.Resource, source.Source, sink.Sink] = Field(default=None, init=False)
    finished_process: events.Event = Field(default=None, init=False)
    product_info: ProductInfo = ProductInfo()

    class Config:
        arbitrary_types_allowed = True

    def update_location(self, resource: Union[resources.NodeData, resources.Resource, source.Source, sink.Sink]):
        """
        Updates the location of the product object.

        Args:
            resource (Location): Location of the product object.
        """
        self.current_location = resource
        logger.debug({"ID": self.product_data.ID, "sim_time": self.env.now, "resource": self.current_location.data.ID, "event": f"Updated location to {self.current_location.data.ID}"})

    def process_product(self):
        self.finished_process = events.Event(self.env)
        self.product_info.log_create_product(
            resource=self.current_location, _product=self, event_time=self.env.now
        )
        """
        Processes the product object in a simpy process. The product object is processed after creation until all required production processes are performed and it reaches a sink.
        """
        logger.debug({"ID": self.product_data.ID, "sim_time": self.env.now, "event": f"Start processing of product"})
        self.set_next_production_process()
        while self.next_prodution_process:
            production_request = self.get_request_for_production_process()
            yield self.env.process(self.product_router.route_request(production_request))
            transport_request = self.get_request_for_transport_process(production_request)
            yield self.env.process(self.product_router.route_request(transport_request))
            yield self.env.process(self.request_process(transport_request))
            yield self.env.process(self.request_process(production_request))
            self.set_next_production_process()
        transport_to_sink_request = self.get_request_for_transport_to_sink()
        yield self.env.process(self.product_router.route_request(transport_to_sink_request))
        yield self.env.process(self.request_process(transport_to_sink_request))
        self.product_info.log_finish_product(
            resource=self.current_location, _product=self, event_time=self.env.now
        )
        self.current_location.register_finished_product(self)
        logger.debug({"ID": self.product_data.ID, "sim_time": self.env.now, "event": f"Finished processing of product"})

    def get_request_for_production_process(self) -> request.Request:
        """
        Returns a request for the next production process of the product object.

        Returns:
            request.Request: The request for the next production process.
        """
        return request.Request(
            process=self.next_prodution_process,
            product=self,
        )
    
    def get_request_for_transport_process(self, production_request: request.Request) -> request.Request:
        """
        Returns a request for the next transport process of the product object.

        Returns:
            request.Request: The request for the next transport process.
        """
        return request.TransportResquest(
            process=self.transport_process,
            product=self,
            origin=self.current_location,
            target=production_request.resource,
        )
    
    def get_request_for_transport_to_sink(self) -> request.Request:
        """
        Returns a request for the transport to the sink of the product object.

        Returns:
            request.Request: The request for the transport to the sink.
        """
        return request.TransportResquest(
            process=self.transport_process,
            product=self,
            origin=self.current_location,
            target=self.product_router.get_sink(self.product_data.product_type),
        )

    def request_process(self, processing_request: request.Request) -> Generator:
        """
        Requests the next production process of the product object from the next production resource by creating a request event and registering it at the environment.
        """
        if isinstance(processing_request, request.TransportResquest):
            type_ = state.StateTypeEnum.transport
        else:
            type_ = state.StateTypeEnum.production
        logger.debug({"ID": self.product_data.ID, "sim_time": self.env.now, "resource": processing_request.resource.data.ID, "event": f"Request process {processing_request.process.process_data.ID} for {type_}"})
        self.env.request_process_of_resource(
            request=processing_request
        )
        yield self.finished_process
        logger.debug({"ID": self.product_data.ID, "sim_time": self.env.now, "resource": processing_request.resource.data.ID, "event": f"Finished process {processing_request.process.process_data.ID} for {type_}"})
        self.product_info.log_end_process(
            resource=processing_request.resource,
            _product=self,
            event_time=self.env.now,
            state_type=type_,
        )
        self.finished_process = events.Event(self.env)

    def set_next_production_process(self):
        """
        Sets the next process of the product object based on the current state of the product and its process model.
        """
        next_possible_processes = self.process_model.get_next_possible_processes()
        if not next_possible_processes:
            self.next_prodution_process = None
            logger.debug({"ID": self.product_data.ID, "sim_time": self.env.now, "event": f"No next process"})
        else:
            self.next_prodution_process = np.random.choice(next_possible_processes)  # type: ignore
            self.process_model.update_marking_from_transition(self.next_prodution_process)  # type: ignore
            logger.debug({"ID": self.product_data.ID, "sim_time": self.env.now, "event": f"Next process {self.next_prodution_process.process_data.ID}"})
