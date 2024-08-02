from typing import Union, Optional, Generator, List

from pydantic import BaseModel, ConfigDict, Field

import logging
logger = logging.getLogger(__name__)

import numpy as np
from simpy import events

from prodsys.models import product_data

from prodsys.simulation import (
    request,
    process,
    router,
    resources,
    sim,
    sink,
    source,
    proces_models,
    node
)
from prodsys.simulation.state import StateTypeEnum, StateEnum

class ProductInfo(BaseModel):
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
    activity: StateEnum = Field(init=False, default=None)
    product_ID: str = Field(init=False, default=None)
    state_type: StateTypeEnum = Field(init=False, default=None)

    model_config=ConfigDict(extra="allow")

    def log_finish_product(
        self,
        resource: Union[resources.Resource, sink.Sink, source.Source],
        _product: "Product",
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
        self.activity = StateEnum.finished_product
        self.state_type = StateTypeEnum.sink

    def log_create_product(
        self,
        resource: Union[resources.Resource, sink.Sink, source.Source],
        _product: "Product",
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
        self.activity = StateEnum.created_product
        self.state_type = StateTypeEnum.source

    def log_start_process(
        self,
        resource: resources.Resource,
        _product: "Product",
        event_time: float,
        state_type: StateTypeEnum,
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
        self.activity = StateEnum.start_state
        self.state_type = state_type

    def log_end_process(
        self,
        resource: resources.Resource,
        _product: "Product",
        event_time: float,
        state_type: StateTypeEnum,
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
        self.activity = StateEnum.end_state
        self.state_type = state_type

Locatable= Union[resources.Resource, node.Node, source.Source, sink.Sink]

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
    transport_process: Union[process.TransportProcess, process.RequiredCapabilityProcess, process.LinkTransportProcess]
    product_router: router.Router

    next_prodution_process: Optional[process.PROCESS_UNION] = Field(default=None, init=False)
    processes_needing_rework: List[process.Process] = Field(default_factory=list, init=False)
    process: events.Process = Field(default=None, init=False)
    current_locatable: Locatable = Field(default=None, init=False)
    finished_process: events.Event = Field(default=None, init=False)
    product_info: ProductInfo = Field(default_factory=ProductInfo, init=False)
    rework_needed: bool = Field(default=False, init=False)
    blocking: bool = Field(default=None, init=False)
    executed_production_processes: List = Field(default_factory=list, init=False)

    model_config=ConfigDict(arbitrary_types_allowed=True)

    def update_location(self, resource: Locatable):
        """
        Updates the location of the product object.

        Args:
            resource (Locatable): Locatable objects where product object currently is.
        """
        self.current_locatable = resource
        logger.debug({"ID": self.product_data.ID, "sim_time": self.env.now, "resource": self.current_locatable.data.ID, "event": f"Updated location to {self.current_locatable.data.ID}"})

    def process_product(self):
        self.finished_process = events.Event(self.env)
        self.product_info.log_create_product(
            resource=self.current_locatable, _product=self, event_time=self.env.now
        )
        """
        Processes the product object in a simpy process. The product object is processed after creation until all required production processes are performed and it reaches a sink.
        """
        logger.debug({"ID": self.product_data.ID, "sim_time": self.env.now, "event": f"Start processing of product"})
        self.set_next_production_process()
        while self.next_prodution_process:
            while True:
                production_request = yield self.env.process(self.product_router.route_product_to_production_resource(self))
                if not production_request:
                    yield self.env.timeout(0)
                    continue
                break
            while True:
                transport_request = yield self.env.process(self.product_router.route_transport_resource_for_product(self, production_request))
                if not transport_request:
                    yield self.env.timeout(0)
                    continue
                break
            yield self.env.process(self.request_process(transport_request))
            yield self.env.process(self.request_process(production_request))
            self.set_next_production_process()
        while True:
            transport_to_sink_request = yield self.env.process(self.product_router.route_product_to_sink(self))
            if not transport_to_sink_request:
                yield self.env.timeout(0)
                continue
            break
        yield self.env.process(self.request_process(transport_to_sink_request))
        self.product_info.log_finish_product(
            resource=self.current_locatable, _product=self, event_time=self.env.now
        )
        self.current_locatable.register_finished_product(self)
        logger.debug({"ID": self.product_data.ID, "sim_time": self.env.now, "event": f"Finished processing of product"})

    def request_process(self, processing_request: request.Request) -> Generator:
        """
        Requests the next production process of the product object from the next production resource by creating a request event and registering it at the environment.
        """
        if isinstance(processing_request, request.TransportResquest):
            type_ = StateTypeEnum.transport
        else:
            type_ = StateTypeEnum.production
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
        blocked = bool
        if self.blocking is not None:
            blocked = self.blocking 
        reworked = self.rework_needed
        
        next_possible_processes = self.process_model.get_next_possible_processes()
        
        if not next_possible_processes:
            self.next_prodution_process = None
            logger.debug({"ID": self.product_data.ID, "sim_time": self.env.now, "event": f"No next process"})  
        else:
            if reworked:         
                if blocked is not None and blocked is True:
                    failed_process = self.next_prodution_process
                    next_possible_processes = self.product_router.get_rework_processes(self, failed_process)
                    if next_possible_processes is not None:
                        self.next_prodution_process = next_possible_processes[0]
                        self.process_model.update_marking_from_transition(self.next_prodution_process)  # type: ignore
                        reworked = False
                        blocked = False
                        logger.debug({"ID": self.product_data.ID, "sim_time": self.env.now, "event": f"Next process {self.next_prodution_process.process_data.ID}"})
                elif blocked is not None and blocked is False:
                    for proc in self.processes_needing_rework:
                        ids_to_rework = [proc.process_data.ID]
                        processes_on_product = self.executed_production_processes
                        if all(id in processes_on_product for id in ids_to_rework):
                            self.next_prodution_process = proc
                            self.process_model.update_marking_from_transition(self.next_prodution_process)              
                    reworked = False
            else: 
                self.next_prodution_process = np.random.choice(next_possible_processes)  # type: ignore
                self.process_model.update_marking_from_transition(self.next_prodution_process)  # type: ignore
                self.executed_production_processes.append(self.next_prodution_process.process_data.ID)
                logger.debug({"ID": self.product_data.ID, "sim_time": self.env.now, "event": f"Next process {self.next_prodution_process.process_data.ID}"})
