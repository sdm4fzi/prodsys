
from __future__ import annotations

from typing import Generator, TYPE_CHECKING, Optional

import logging

from prodsys.simulation import (
    sim,
    process,
)

from prodsys.simulation.process import (
    ReworkProcess,
)

from prodsys.models.dependency_data import DependencyType
if TYPE_CHECKING:
    from prodsys.simulation import (
        process,
    )
    from prodsys.simulation import request as request_module
    from prodsys.simulation.resources import SystemResource
    from prodsys.simulation.router import Router

logger = logging.getLogger(__name__)

class SystemProcessModelHandler:
    """
    A process model handler is responsible for controlling process models that can contain multiple processes
    with complex dependencies and execution patterns (DAG structures).
    """

    def __init__(self, env: sim.Environment) -> None:
        self.env = env
        self.resource = None

        self.process_model = None
        self.next_possible_processes: Optional[list[process.PROCESS_UNION]] = None
        self.processes_needing_rework: list[process.Process] = []
        self.blocking_rework_process_mappings: list[
            list[process.PROCESS_UNION, list[process.ReworkProcess]]
        ] = []
        self.non_blocking_rework_process_mappings: list[
            list[process.PROCESS_UNION, list[process.ReworkProcess]]
        ] = []
        self.executed_production_processes: list[str] = []

    def get_products_of_lot(
        self, lot_requests: list[request_module.Request]
    ) -> Generator:
        """
        Get the next product for a process. The product is removed (get) from the input queues of the resource.
        """
        for lot_request in lot_requests:
            yield from lot_request.origin_queue.get(lot_request.entity.data.ID)

    def put_entities_of_request(
        self, process_request: request_module.Request
    ) -> Generator:
        """
        Place a product to the output queue (put) of the resource.

        Args:
            process_request (request_module.Request): The request to place the product to.

        Returns:
            Generator: The generator yields when the product is placed in the queue (multiple events for multiple products, e.g. for a batch process or an assembly).
        """
        required_assembly_types = [dependency.data.required_entity for dependency in process_request.required_dependencies if dependency.data.dependency_type == DependencyType.ASSEMBLY]
        for dependant_entity in process_request.entity.depended_entities:
            if dependant_entity.data.type not in required_assembly_types:
                continue    
            dependant_entity.info.log_consumption(dependant_entity.current_locatable, dependant_entity, self.env.now)
        required_tool_types = [dependency.data.required_entity for dependency in process_request.required_dependencies if dependency.data.dependency_type == DependencyType.TOOL]
        for dependant_entity in process_request.entity.depended_entities:
            if dependant_entity.data.type not in required_tool_types:
                continue
            dependant_entity.update_location(process_request.entity._current_locatable)
            dependant_entity.info.log_start_unloading(dependant_entity.current_locatable, dependant_entity, self.env.now, dependant_entity.current_locatable)
            yield from dependant_entity.current_locatable.put(dependant_entity.data)
            dependant_entity.info.log_end_unloading(dependant_entity.current_locatable, dependant_entity, self.env.now, dependant_entity.current_locatable)


    def handle_request(self, process_request: request_module.Request) -> Generator:
        """
        Handle a process model request by executing the processes according to the DAG structure.

        Args:
            process_request (request_module.Request): The process model request.

        Yields:
            Generator: The generator yields when the process model is finished.
        """
        resource: SystemResource = process_request.get_resource()
        self.resource = resource
        proc = process_request.get_process()
        self.process_model = proc.precedence_graph.create_instance()
        
        entity = process_request.get_entity()
        target_queue = process_request.target_queue

        super_system_router = process_request.entity.router
        system_router = resource.router
        process_request.entity.router = system_router

        assert process_request.entity._current_locatable == process_request.origin_queue, f"Product {entity.data.ID} is not at the origin queue {process_request.origin_queue}"
        
        if process_request.required_dependencies:
            yield process_request.request_dependencies()
        
        yield from resource.setup(proc)

        resource.controller.mark_started_process(process_request.capacity_required)
        # TODO: add logging to start and end of process model handling for product entity
        self.set_next_possible_production_processes()
        while self.next_possible_processes:
            executed_process_event = system_router.request_process_step(entity, self.next_possible_processes)
            yield executed_process_event
            # Check if rework is required based on the state's failure determination
            # The state has already determined and logged if the process failed
            if not isinstance(entity.current_process, ReworkProcess):
                # Check if the process failed (determined by the state)
                if entity.last_process_failed:
                    self.add_needed_rework(entity.current_process, system_router)
            elif isinstance(entity.current_process, ReworkProcess):
                self.register_rework(entity.current_process)
            self.update_executed_process(entity.current_process)
            # Reset failure status for next process
            entity.last_process_failed = None
            self.set_next_possible_production_processes()
        
        # After all internal processes are complete, set the entity's current_process to this ProcessModelProcess
        # This ensures that when control returns to a parent handler, it sees the ProcessModelProcess as completed,
        # not the last internal process that was executed
        entity.current_process = proc
        
        if(entity.no_transport_to_sink):
            sink = entity.router.route_disassembled_product_to_sink(entity)
        else:
            arrived_at_queue = system_router.request_transport(entity, target_queue)
            yield arrived_at_queue
        yield from self.put_entities_of_request(process_request)
        process_request.entity.update_location(process_request.target_queue)
        process_request.entity.router = super_system_router
        process_request.entity.router.mark_finished_request(process_request)
        self.resource.controller.mark_finished_process(process_request.capacity_required)


    def add_needed_rework(self, failed_process: process.PROCESS_UNION, router: Router) -> None:
        """
        Adds a process to the list of processes that need rework.

        Args:
            entity: The entity (product) that needs rework.
            failed_process (PROCESS_UNION): Process that needs rework.
        """
        self.processes_needing_rework.append(failed_process)
        possible_rework_processes = router.get_rework_processes(
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

    def register_rework(self, rework_process: process.ReworkProcess) -> None:
        """
        Register a rework process that has been executed.
        
        Args:
            rework_process (process.ReworkProcess): The rework process that has been executed.
        """
        reworked_process = None
        for process_rework_mapping in (
            self.blocking_rework_process_mappings
            + self.non_blocking_rework_process_mappings
        ):
            if rework_process not in process_rework_mapping[1]:
                continue
            reworked_process = process_rework_mapping[0]
            break
        
        if reworked_process is None:
            raise ValueError(f"Rework process {rework_process.data.ID} not found in rework mappings")
            
        if reworked_process in self.processes_needing_rework:
            self.processes_needing_rework.remove(reworked_process)
        
        in_blocking_list = any(
            reworked_process == process_rework_mapping[0]
            for process_rework_mapping in self.blocking_rework_process_mappings
        )
        if in_blocking_list:
            mapping_to_adjust = self.blocking_rework_process_mappings
        else:
            mapping_to_adjust = self.non_blocking_rework_process_mappings
        
        index_to_remove = None
        for index, process_rework_mapping in enumerate(mapping_to_adjust):
            if reworked_process == process_rework_mapping[0]:
                index_to_remove = index
                break
        
        if index_to_remove is None:
            raise ValueError(f"Rework process {rework_process.data.ID} not found in rework mappings")
        mapping_to_adjust.pop(index_to_remove)

    def update_executed_process(self, executed_process: process.PROCESS_UNION) -> None:
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
                possible_rework_processes = process_mapping[1]
                next_possible_processes += possible_rework_processes
            self.next_possible_processes = next_possible_processes
            return

        next_possible_processes = self.process_model.get_next_possible_processes()

        # if all normal processes are done, i.e. the product has finished its process sequence, execute rework processes without blocking.
        if not next_possible_processes and self.non_blocking_rework_process_mappings:
            next_possible_processes = []
            for process_mapping in self.non_blocking_rework_process_mappings:
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