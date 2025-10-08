
from __future__ import annotations

from typing import Generator, TYPE_CHECKING, Optional

import logging

from prodsys.simulation import (
    sim,
    process,
)

if TYPE_CHECKING:
    from prodsys.simulation import (
        process,
    )
    from prodsys.simulation import request as request_module

logger = logging.getLogger(__name__)

class ProcessModelHandler:
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

    def handle_request(self, process_request: request_module.Request) -> Generator:
        """
        Handle a process model request by executing the processes according to the DAG structure.

        Args:
            process_request (request_module.Request): The process model request.

        Yields:
            Generator: The generator yields when the process model is finished.
        """
        resource = process_request.get_resource()
        self.resource = resource
        proc = process_request.get_process()
        self.process_model = proc.precedence_graph
        entity = process_request.get_entity()
        target_queue = process_request.target_queue

        if hasattr(resource.data, "subresource_ids"):
            router = resource.router
        else:
            router = entity.router
        
        if process_request.required_dependencies:
            yield process_request.request_dependencies()
        
        yield from resource.setup(proc)

        resource.controller.mark_started_process(process_request.capacity_required)

        self.set_next_possible_production_processes()
        while self.next_possible_processes:
            executed_process_event = router.request_process_step(entity, self.next_possible_processes)
            yield executed_process_event
            if hasattr(entity.current_process, "reworked_process_ids"):
                self.add_needed_rework(entity.current_process)
            self.update_executed_process(entity.current_process)
            self.set_next_possible_production_processes()
        arrived_at_queue = router.request_transport(entity, target_queue)
        yield arrived_at_queue
        process_request.entity.router.mark_finished_request(process_request)
        self.resource.controller.mark_finished_process(process_request.capacity_required)

    def add_needed_rework(self, failed_process: process.PROCESS_UNION) -> None:
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

    def register_rework(self, rework_process: process.ReworkProcess) -> None:
        """
        Register a rework process that has been executed.
        """
        for process_rework_mapping in (
            self.blocking_rework_process_mappings
            + self.non_blocking_rework_process_mappings
        ):
            if rework_process not in process_rework_mapping[1]:
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