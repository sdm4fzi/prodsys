import random
from typing import Union, Optional, Generator, List

from pydantic import BaseModel, ConfigDict, Field

import logging

logger = logging.getLogger(__name__)

from simpy import events

from prodsys.models import product_data

from prodsys.simulation import (
    request,
    auxiliary,
    process,
    router,
    resources,
    sim,
    sink,
    store,
    source,
    proces_models,
    node,
)
from prodsys.simulation.state import StateTypeEnum, StateEnum
from prodsys.simulation.process import PROCESS_UNION, ReworkProcess


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

    model_config = ConfigDict(extra="allow")

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


Locatable = Union[resources.Resource, node.Node, source.Source, sink.Sink, store.Store]


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
    transport_process: Union[
        process.TransportProcess,
        process.RequiredCapabilityProcess,
        process.LinkTransportProcess,
    ]
    product_router: router.Router

    next_prodution_process: Optional[process.PROCESS_UNION] = Field(
        default=None, init=False
    )
    processes_needing_rework: List[process.Process] = Field(
        default_factory=list, init=False
    )
    blocking_rework_process_mappings: list[
        list[process.PROCESS_UNION, list[ReworkProcess]]
    ] = Field(default_factory=list, init=False)
    non_blocking_rework_process_mappings: list[
        list[process.PROCESS_UNION, list[ReworkProcess]]
    ] = Field(default_factory=list, init=False)
    process: events.Process = Field(default=None, init=False)
    current_locatable: Locatable = Field(default=None, init=False)
    finished_process: events.Event = Field(default=None, init=False)
    product_info: ProductInfo = Field(default_factory=ProductInfo, init=False)
    executed_production_processes: List = Field(default_factory=list, init=False)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def update_location(self, locatable: Locatable):
        """
        Updates the location of the product object.

        Args:
            locatable (Locatable): Locatable objects where product object currently is.
        """
        self.current_locatable = locatable
        logger.debug(
            {
                "ID": self.product_data.ID,
                "sim_time": self.env.now,
                "resource": self.current_locatable.data.ID,
                "event": f"Updated location to {self.current_locatable.data.ID}",
            }
        )

    def process_product(self):
        self.finished_process = events.Event(self.env)
        self.product_info.log_create_product(
            resource=self.current_locatable, _product=self, event_time=self.env.now
        )
        """
        Processes the product object in a simpy process. The product object is processed after creation until all required production processes are performed and it reaches a sink.
        """
        logger.debug(
            {
                "ID": self.product_data.ID,
                "sim_time": self.env.now,
                "event": f"Start processing of product",
            }
        )
        self.set_next_production_process()

        if self.product_data.auxiliaries:
            while True:
                auxiliary_request: request.AuxiliaryRequest = yield self.env.process(
                    self.product_router.route_auxiliary_to_product(self)
                )
                if not auxiliary_request:
                    yield self.env.timeout(0)
                    continue
                break
            logger.debug(
                {
                    "ID": self.product_data.ID,
                    "sim_time": self.env.now,
                    "resource": auxiliary_request.resource.data.ID,
                    "aux": auxiliary_request.auxiliary.product_data.ID,
                    "process": auxiliary_request.process.process_data.ID,
                    "event": f"auxiliary request for {auxiliary_request.product.product_data.ID}",
                }
            )
            while True:
                auxiliary_transport_request: request.TransportResquest = (
                    yield self.env.process(
                        self.product_router.route_transport_resource_for_item(
                            auxiliary_request
                        )
                    )
                )
                if not auxiliary_transport_request:
                    yield self.env.timeout(0)
                    continue
                break
            logger.debug(
                {
                    "ID": self.product_data.ID,
                    "sim_time": self.env.now,
                    "resource": auxiliary_transport_request.resource.data.ID,
                    "aux": auxiliary_transport_request.product.product_data.ID,
                    "process": auxiliary_transport_request.process.process_data.ID,
                    "origin": auxiliary_transport_request.origin.data.ID,
                    "target": auxiliary_transport_request.target.data.ID,
                    "event": f"starting auxiliary transport request for {auxiliary_transport_request.product.product_data.ID}",
                }
            )
            yield self.env.process(
                auxiliary_request.auxiliary.request_process(auxiliary_transport_request)
            )
            logger.debug(
                {
                    "ID": self.product_data.ID,
                    "sim_time": self.env.now,
                    "resource": auxiliary_transport_request.resource.data.ID,
                    "aux": auxiliary_transport_request.product.product_data.ID,
                    "process": auxiliary_transport_request.process.process_data.ID,
                    "origin": auxiliary_transport_request.origin.data.ID,
                    "target": auxiliary_transport_request.target.data.ID,
                    "event": f"finished waiting for auxiliary transport request for {auxiliary_transport_request.product.product_data.ID}",
                }
            )

        while self.next_prodution_process:
            logger.debug(
                {
                    "ID": self.product_data.ID,
                    "sim_time": self.env.now,
                    "process": self.next_prodution_process.process_data.ID,
                    "event": f"Start process of product",
                }
            )
            while True:
                production_request = yield self.env.process(
                    self.product_router.route_product_to_production_resource(self)
                )
                if not production_request:
                    yield self.env.timeout(0)
                    continue
                break
            while True:
                transport_request = yield self.env.process(
                    self.product_router.route_transport_resource_for_item(
                        production_request
                    )
                )
                if not transport_request:
                    yield self.env.timeout(0)
                    continue
                break
            yield self.env.process(self.request_process(transport_request))
            yield self.env.process(self.request_process(production_request))
            store_product = self.product_router.check_store_product(self)
            if store_product:
                logger.debug(
                    {
                        "ID": self.product_data.ID,
                        "sim_time": self.env.now,
                        "event": f"Store product in storage",
                    }
                )
                while True:
                    transport_to_storage_request = yield self.env.process(
                        self.product_router.route_product_to_storage(self)
                    )
                    if not transport_to_storage_request:
                        yield self.env.timeout(0)
                        continue
                    break
                yield self.env.process(
                    self.request_process(transport_to_storage_request)
                )
                logger.debug(
                    {
                        "ID": self.product_data.ID,
                        "sim_time": self.env.now,
                        "event": f"Product transported to storage",
                    }
                )

            self.set_next_production_process()
        while True:
            transport_to_sink_request = yield self.env.process(
                self.product_router.route_product_to_sink(self)
            )
            if not transport_to_sink_request:
                yield self.env.timeout(0)
                continue
            break
        yield self.env.process(self.request_process(transport_to_sink_request))
        self.product_info.log_finish_product(
            resource=self.current_locatable, _product=self, event_time=self.env.now
        )
        self.current_locatable.register_finished_product(self)
        logger.debug(
            {
                "ID": self.product_data.ID,
                "sim_time": self.env.now,
                "event": f"Finished processing of product",
            }
        )

        if self.product_data.auxiliaries:
            auxiliary_request.auxiliary.update_location(self.current_locatable)
            while True:
                auxiliary_transport_request: request.TransportResquest = (
                    yield self.env.process(
                        self.product_router.route_auxiliary_to_store(
                            auxiliary_request.auxiliary
                        )
                    )
                )
                if not auxiliary_request:
                    yield self.env.timeout(0)
                    continue
                break
            logger.debug(
                {
                    "ID": self.product_data.ID,
                    "sim_time": self.env.now,
                    "resource": auxiliary_transport_request.resource.data.ID,
                    "aux": auxiliary_transport_request.product.product_data.ID,
                    "process": auxiliary_transport_request.process.process_data.ID,
                    "origin": auxiliary_transport_request.origin.data.ID,
                    "target": auxiliary_transport_request.target.data.ID,
                    "event": f"starting auxiliary transport request for {auxiliary_transport_request.product.product_data.ID}",
                }
            )
            yield self.env.process(
                auxiliary_request.auxiliary.request_process(auxiliary_transport_request)
            )
            auxiliary_request.auxiliary.release_auxiliary_from_product()

    def request_process(self, processing_request: request.Request) -> Generator:
        """
        Requests the next production process of the product object from the next production resource by creating a request event and registering it at the environment.
        """
        if isinstance(processing_request, request.TransportResquest):
            type_ = StateTypeEnum.transport
        else:
            type_ = StateTypeEnum.production
        logger.debug(
            {
                "ID": self.product_data.ID,
                "sim_time": self.env.now,
                "resource": processing_request.resource.data.ID,
                "event": f"Request process {processing_request.process.process_data.ID} for {type_}",
            }
        )
        self.env.request_process_of_resource(request=processing_request)
        yield self.finished_process
        logger.debug(
            {
                "ID": self.product_data.ID,
                "sim_time": self.env.now,
                "resource": processing_request.resource.data.ID,
                "event": f"Finished process {processing_request.process.process_data.ID} for {type_}",
            }
        )
        self.product_info.log_end_process(
            resource=processing_request.resource,
            _product=self,
            event_time=self.env.now,
            state_type=type_,
        )
        self.finished_process = events.Event(self.env)
        if isinstance(processing_request.process, process.ReworkProcess):
            self.register_rework(processing_request.process)

    def add_needed_rework(self, failed_process: PROCESS_UNION) -> None:
        """
        Adds a process to the list of processes that need rework.

        Args:
            failed_process (PROCESS_UNION): Process that needs rework.
        """
        self.processes_needing_rework.append(failed_process)
        possible_rework_processes = self.product_router.get_rework_processes(
            self, failed_process
        )
        if not possible_rework_processes:
            raise ValueError(
                f"No rework processes found for process {failed_process.process_data.ID}"
            )
        if any(rework_process.blocking for rework_process in possible_rework_processes):
            self.blocking_rework_process_mappings.append(
                [failed_process, possible_rework_processes]
            )
        else:
            self.non_blocking_rework_process_mappings.append(
                [failed_process, possible_rework_processes]
            )

    def register_rework(self, rework_process: ReworkProcess) -> None:
        """
        Register a rework process that has been executed.
        """
        for process_rework_mapping in (
            self.blocking_rework_process_mappings
            + self.non_blocking_rework_process_mappings
        ):
            if not rework_process in process_rework_mapping[1]:
                continue
            reworked_process = process_rework_mapping[0]
            break
        self.processes_needing_rework.remove(reworked_process)
        in_blocking_list = any(
            reworked_process == process_rework_mapping[0]
            for process_rework_mapping in self.blocking_rework_process_mappings
        )
        if in_blocking_list:
            mapping_to_adjust = self.blocking_rework_process_mappings
        else:
            mapping_to_adjust = self.non_blocking_rework_process_mappings
        for index, process_rework_mapping in enumerate(mapping_to_adjust):
            if reworked_process == process_rework_mapping[0]:
                index_to_remove = index
                break
        mapping_to_adjust.pop(index_to_remove)

    def set_next_production_process(self):
        """
        Sets the next process of the product object based on the current state of the product and its process model.
        """
        # check if rework is needed due to blocking rework processes. If so, execute these rework processes
        if self.blocking_rework_process_mappings:
            process_mapping_to_rework = random.choice(
                self.blocking_rework_process_mappings
            )
            next_possible_processes = process_mapping_to_rework[1]
            self.next_prodution_process = random.choice(next_possible_processes)
            logger.debug(
                {
                    "ID": self.product_data.ID,
                    "sim_time": self.env.now,
                    "event": f"Blocking rework as next process with ID {self.next_prodution_process.process_data.ID}",
                }
            )
            return

        next_possible_processes = self.process_model.get_next_possible_processes()

        # if all normal processes are done, i.e. the product has finished its process sequence, execute rework processes without blocking.
        if not next_possible_processes and self.non_blocking_rework_process_mappings:
            process_mapping_to_rework = random.choice(
                self.non_blocking_rework_process_mappings
            )
            failed_process = process_mapping_to_rework[0]
            next_possible_processes = process_mapping_to_rework[1]
            self.next_prodution_process = random.choice(next_possible_processes)
            logger.debug(
                {
                    "ID": self.product_data.ID,
                    "sim_time": self.env.now,
                    "event": f"Non-blocking rework as next process with ID {self.next_prodution_process.process_data.ID}",
                }
            )
            return
        # if all normal processes are done and no rework processes are needed, the product has finished its process sequence.
        if not next_possible_processes:
            self.next_prodution_process = None
            return

        self.next_prodution_process = random.choice(next_possible_processes)  # type: ignore
        self.process_model.update_marking_from_transition(self.next_prodution_process)  # type: ignore
        self.executed_production_processes.append(
            self.next_prodution_process.process_data.ID
        )
        logger.debug(
            {
                "ID": self.product_data.ID,
                "sim_time": self.env.now,
                "event": f"Next process {self.next_prodution_process.process_data.ID}",
            }
        )
