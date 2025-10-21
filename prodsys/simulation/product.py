from __future__ import annotations

import random
from typing import TYPE_CHECKING, Callable, Union, Optional, Generator, List

import logging

from prodsys.models.source_data import RoutingHeuristic

logger = logging.getLogger(__name__)

from simpy import events

from prodsys.models import product_data
from prodsys.simulation.dependency import DependencyInfo

if TYPE_CHECKING:
    from prodsys.simulation.dependency import DependedEntity, Dependency
    from prodsys.simulation import (
        primitive,
        process_models,
        request,
        process,
        router,
        resources,
        sim,
        sink,
        source,
        node,
    )
    from prodsys.simulation.process import PROCESS_UNION, ReworkProcess


class ProductInfo:
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

    def __init__(
        self,
        resource_ID: str = None,
        state_ID: str = None,
        event_time: float = None,
        activity: StateEnum = None,
        product_ID: str = None,
        state_type: StateTypeEnum = None,
    ):
        self.resource_ID = resource_ID
        self.state_ID = state_ID
        self.event_time = event_time
        self.activity = activity
        self.product_ID = product_ID
        self.state_type = state_type

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
        self.product_ID = _product.data.ID
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
        self.product_ID = _product.data.ID
        self.activity = StateEnum.created_product
        self.state_type = StateTypeEnum.source

    def log_bind(
        self,
        resource: resources.Resource,
        _product: "Product",
        event_time: float,
    ) -> None:
        """
        Logs the start of the usage of a product.

        Args:
            resource (resources.Resource): Resource that the product is processed at.
            _product (Product): Product that is processed.
            event_time (float): Time of the event.
        """
        # TODO: implement logging for product dependency usage
        # self.resource_ID = resource.data.ID
        # self.state_ID = resource.data.ID
        # self.event_time = event_time
        # self.product_ID = _product.data.ID
        # self.activity = StateEnum.started_product_usage
        # self.state_type = StateTypeEnum.production
        pass

    def log_release(
        self,
        resource: resources.Resource,
        _product: "Product",
        event_time: float,
    ) -> None:
        """
        Logs the end of the usage of a product.

        Args:
            resource (resources.Resource): Resource that the product is processed at.
            _product (Product): Product that is processed.
            event_time (float): Time of the event.
        """
        # self.resource_ID = resource.data.ID
        # self.state_ID = resource.data.ID
        # self.event_time = event_time
        # self.product_ID = _product.data.ID
        # self.activity = StateEnum.finished_product_usage
        # self.state_type = StateTypeEnum.production
        pass


class Product:
    """
    Class that represents a product in the discrete event simulation. For easier instantion of the class, use the ProductFactory at prodsys.factories.product_factory.

    Args:
        env (sim.Environment): prodsys simulation environment.
        product_data (product_data.ProductData): Product data that represents the meta information of the simulation product object.
        process_model (proces_models.ProcessModel): Process model that represents the required manufacturing processes and the current state of the product.
        transport_process (process.Process): Transport process that represents the required transport processes.
        product_router (router.Router): Router that is used to route the product object.
    """

    def __init__(
        self,
        env: sim.Environment,
        data: product_data.ProductData,
        process_model: process_models.ProcessModel,
        transport_process: Union[
            process.TransportProcess,
            process.RequiredCapabilityProcess,
            process.LinkTransportProcess,
        ],
        product_router: router.Router,
        routing_heuristic: RoutingHeuristic,
        dependencies: Optional[List[Dependency]] = None,
    ):
        self.env = env
        self.data = data
        self.process_model = process_model
        self.transport_process = transport_process
        self.router = product_router
        self.routing_heuristic = routing_heuristic

        self.dependencies: Optional[List[Dependency]] = dependencies
        self.depended_entities: List[DependedEntity] = []

        self.current_locatable: Locatable = None
        self.current_process: Optional[process.PROCESS_UNION] = None
        self.next_possible_processes: Optional[list[process.PROCESS_UNION]] = None
        self.processes_needing_rework: List[process.Process] = []
        self.blocking_rework_process_mappings: list[
            list[process.PROCESS_UNION, list[ReworkProcess]]
        ] = []
        self.non_blocking_rework_process_mappings: list[
            list[process.PROCESS_UNION, list[ReworkProcess]]
        ] = []
        self.process: events.Process = None
        self.info: ProductInfo = ProductInfo()
        self.executed_production_processes: List = []
        self.bound = False
        self.being_bound = events.Event(self.env)
        self.got_free = events.Event(self.env)
        self.dependency_info = DependencyInfo(primitive_id=self.data.ID)
        

    def update_location(self, locatable: Locatable):
        """
        Updates the location of the product object.

        Args:
            locatable (Locatable): Locatable objects where product object currently is.
        """
        self.current_locatable = locatable

    def process_product(self):
        self.info.log_create_product(
            resource=self.current_locatable, _product=self, event_time=self.env.now
        )
        """
        Processes the product object in a simpy process. The product object is processed after creation until all required production processes are performed and it reaches a sink.
        """
        self.set_next_possible_production_processes()
        if self.dependencies:
            dep_request_infos = (
                self.router.get_dependencies_for_product_processing(self)
            )
            for dependency in dep_request_infos:
                yield dependency.request_completion_event
            for dependenant_item in self.depended_entities:
                # TODO: make this assigning of dependencies to product and placing them in queues / removing in extra class that handles this
                yield from dependenant_item.current_locatable.get(dependenant_item.data.ID)
                dependenant_item.current_locatable = self

        while self.next_possible_processes:
            executed_process_event = self.router.request_processing(self)
            yield executed_process_event
            if hasattr(self.current_process, "reworked_process_ids"):
                self.register_rework(self.current_process)
            self.update_executed_process(self.current_process)
            self.set_next_possible_production_processes()
            
            
        arrived_at_sink_event, sink = self.router.route_product_to_sink(self)
        yield arrived_at_sink_event
        
        
        sink.register_finished_product(self)
        if (self.data.becomes_primitive):
            yield self.being_bound
        self.info.log_finish_product(
            resource=self.current_locatable, _product=self, event_time=self.env.now
        )
        
        for dependency in self.depended_entities:
            # TODO: use here interaction handler to select ports
            yield from self.current_locatable.put(dependency.data)
            dependency.current_locatable = self.current_locatable
            dependency.release()   
        
        
    def add_needed_rework(self, failed_process: PROCESS_UNION) -> None:
        """
        Adds a process to the list of processes that need rework.

        Args:
            failed_process (PROCESS_UNION): Process that needs rework.
        """
        self.processes_needing_rework.append(failed_process)
        possible_rework_processes = self.router.get_rework_processes(
            failed_process
        )
        if not possible_rework_processes:
            raise ValueError(
                f"No rework processes found for process {failed_process.data.ID}"
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

    def update_executed_process(self, executed_process: PROCESS_UNION) -> None:
        if not isinstance(executed_process, process.ReworkProcess):
            self.process_model.update_marking_from_transition(executed_process)  # type: ignore
        self.executed_production_processes.append(executed_process.data.ID)

    def set_next_possible_production_processes(self):
        """
        Sets the next process of the product object based on the current state of the product and its process model.
        """
        # check if rework is needed due to blocking rework processes. If so, execute these rework processes
        if self.blocking_rework_process_mappings:
            next_possible_processes = []
            for process_mapping in self.blocking_rework_process_mappings:
                failed_process = process_mapping[0]
                possible_rework_processes = process_mapping[1]
                next_possible_processes += possible_rework_processes
            self.next_possible_processes = next_possible_processes
            return

        next_possible_processes = self.process_model.get_next_possible_processes()

        # if all normal processes are done, i.e. the product has finished its process sequence, execute rework processes without blocking.
        if not next_possible_processes and self.non_blocking_rework_process_mappings:
            next_possible_processes = []
            for process_mapping in self.non_blocking_rework_process_mappings:
                failed_process = process_mapping[0]
                possible_rework_processes = process_mapping[1]
                next_possible_processes += possible_rework_processes
            next_possible_processes = next_possible_processes
            self.next_possible_processes = next_possible_processes
            return
        # if all normal processes are done and no rework processes are needed, the product has finished its process sequence.
        if not next_possible_processes:
            self.next_possible_processes = None
            return

        self.next_possible_processes = next_possible_processes


    def bind(self, dependant: Union[Product, resources.Resource], dependency: Dependency) -> None:
            """
            Reserves the product object.
            """
            if self.bound:
                raise Exception(
                    f"Primitive {self.data.ID} is bound reserved. Cannot bind again."
                )
            self.bound = True
            self.being_bound.succeed()
            self.current_dependant = dependant
            dependant.depended_entities.append(self)
           

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

from prodsys.simulation.state import StateTypeEnum, StateEnum
from prodsys.simulation import port, process


# Locatable = Union[
#         resources.Resource, node.Node, source.Source, sink.Sink, port.Store
#     ]
Locatable=None