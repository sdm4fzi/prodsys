
from __future__ import annotations

from typing import Generator, TYPE_CHECKING, Optional

import logging
import numpy as np

from prodsys.simulation import (
    sim,
    process,
    state,
)

from prodsys.simulation.process import (
    ReworkProcess,
)

if TYPE_CHECKING:
    from prodsys.simulation import (
        process,
        state,
    )
    from prodsys.simulation import request as request_module
    from prodsys.simulation.resources import Resource
    from prodsys.simulation.router import Router

logger = logging.getLogger(__name__)

class ResourceProcessModelHandler:
    """
    A process model handler for regular resources that executes all processes in the model
    sequentially on the same resource. The product is picked up from the origin queue at the 
    beginning and put back in the target queue after all processes are finished.
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

    def get_entities_of_request(
        self, process_request: request_module.Request
    ) -> Generator:
        """
        Get the product from the origin queue. The product is removed (get) from the input queue.

        Args:
            process_request (request_module.Request): The request to get the entities from.

        Yields:
            Generator: The generator yields when the product is taken from the queue.
        """
        entity = process_request.get_entity()
        logger.debug(f"[RESOURCE_PM GET] Time={self.env.now:.2f} | Resource={process_request.resource.data.ID} | Entity={entity.data.ID} | Origin Queue={process_request.origin_queue.data.ID} | Getting entity")
        yield from process_request.origin_queue.get(entity.data.ID)
        logger.debug(f"[RESOURCE_PM GET DONE] Time={self.env.now:.2f} | Resource={process_request.resource.data.ID} | Entity={entity.data.ID} | Successfully got entity")
        # Reserve target queue after getting from origin
        process_request.target_queue.reserve()

    def put_entities_of_request(
        self, process_request: request_module.Request
    ) -> Generator:
        """
        Place the product to the output queue (put) of the resource.

        Args:
            process_request (request_module.Request): The request to place the product to.

        Yields:
            Generator: The generator yields when the product is placed in the queue.
        """
        entity = process_request.get_entity()
        logger.debug(f"[RESOURCE_PM PUT] Time={self.env.now:.2f} | Resource={process_request.resource.data.ID} | Entity={entity.data.ID} | Target Queue={process_request.target_queue.data.ID} | Putting entity")
        yield from process_request.target_queue.put(entity.data)
        logger.debug(f"[RESOURCE_PM PUT DONE] Time={self.env.now:.2f} | Resource={process_request.resource.data.ID} | Entity={entity.data.ID} | Successfully put entity")

    def handle_request(self, process_request: request_module.Request) -> Generator:
        """
        Handle a process model request by executing all processes in the model sequentially
        on the same resource. The product is picked up from origin queue at the beginning
        and put back in target queue after all processes are finished.

        Args:
            process_request (request_module.Request): The process model request.

        Yields:
            Generator: The generator yields when the process model is finished.
        """
        print(f"handling process model request for {process_request.requesting_item.data.ID} on resource {process_request.resource.data.ID}")
        resource: Resource = process_request.get_resource()
        self.resource = resource
        proc = process_request.get_process()
        self.process_model = proc.precedence_graph.create_instance()
        
        entity = process_request.get_entity()
        origin_queue = process_request.origin_queue
        target_queue = process_request.target_queue

        assert entity.current_locatable == origin_queue, f"Product {entity.data.ID} is not at the origin queue {origin_queue.data.ID}"
        
        if process_request.required_dependencies:
            yield process_request.request_dependencies()
        
        # yield from resource.setup(proc)
        
        # Request resource capacity upfront for the entire process model execution
        # This reserves capacity slots that will be used for all processes in the model
        resource_requests = []
        for _ in range(process_request.capacity_required):
            resource_request = resource.request()
            yield resource_request
            resource_requests.append(resource_request)

        # Get product from origin queue at the beginning
        yield from self.get_entities_of_request(process_request)
        entity.update_location(resource)

        resource.controller.mark_started_process(process_request.capacity_required)
        
        # Execute all processes in the model sequentially on this resource
        # Pick up product from origin queue at the beginning (already done above)
        first_process = True
        self.set_next_possible_production_processes()
        while self.next_possible_processes:
            # FIXME: Get dependencies here
            # Execute one process from the available processes (if multiple available, choose first)
            # For regular resources, we execute processes sequentially even if DAG allows parallel execution
            next_process = self.next_possible_processes[0]
            yield from resource.setup(next_process)
            
            # Wait for a free process slot and get the production state
            production_state: state.State = yield from resource.wait_for_free_process(next_process)
            if first_process:
                origin_queue = process_request.origin_queue
                # FIXME: avoid this by logging queue interaction events seperately from state info (make counting wip easier)
                target_queue = None
                first_process = False
            else:
                origin_queue = None
                target_queue = process_request.target_queue
                
                
            production_state.state_info.log_queues(origin_queue, target_queue)
            production_state.reserved = True
            
            # Get process time
            process_time = next_process.time_model.get_next_time()
            
            # Execute the process
            production_state.state_info.log_product(entity, state.StateTypeEnum.production)
            # Update entity's current process to the process being executed
            entity.current_process = next_process
            production_state.process = self.env.process(production_state.process_state(time=process_time))
            production_state.reserved = False
            yield production_state.process
            production_state.process = None
            
            # Check for rework requirement
            if self.is_rework_required(next_process):
                # For resource process models, rework would need to be handled differently
                # For now, we'll skip rework handling in resource process models
                # TODO: Add rework support if needed
                pass
            
            # Update the process model marking after executing this process
            self.update_executed_process(next_process)
            
            # Get next possible processes based on updated marking
            self.set_next_possible_production_processes()

        # After all internal processes are complete, set the entity's current_process to this ProcessModelProcess
        # This ensures that when control returns, it sees the ProcessModelProcess as completed,
        # not the last internal process that was executed
        entity.current_process = proc
        
        # Put product back to target queue after all processes are finished
        yield from self.put_entities_of_request(process_request)
        entity.update_location(process_request.target_queue)

        process_request.entity.router.mark_finished_request(process_request)
        self.resource.controller.mark_finished_process(process_request.capacity_required)
        
        # Release resource capacity requests (must be after marking finished)
        for resource_request in resource_requests:
            resource.release(resource_request)

    def is_rework_required(self, executed_process: process.PROCESS_UNION) -> bool:
        """
        Determine if rework is needed based on the process's failure rate.

        Args:
            executed_process (process.PROCESS_UNION): The process to check for failure rate.
        
        Returns:
            bool: True if rework is required, False otherwise.
        """
        if isinstance(executed_process, ReworkProcess):
            return False
        
        if not hasattr(executed_process.data, 'failure_rate'):
            return False
            
        failure_rate = executed_process.data.failure_rate
        if not failure_rate or failure_rate == 0:
            return False
        
        rework_needed = np.random.choice(
            [True, False], p=[failure_rate, 1 - failure_rate]
        )
        return rework_needed

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