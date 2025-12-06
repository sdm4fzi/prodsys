
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
from prodsys.models.dependency_data import DependencyType

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
        for entity in process_request.get_atomic_entities():
            entity.info.log_start_loading(process_request.resource, entity, self.env.now, process_request.origin_queue)
            yield from process_request.origin_queue.get(entity.data.ID)
            entity.info.log_end_loading(process_request.resource, entity, self.env.now, process_request.origin_queue)
        required_assembly_types = [dependency.data.required_entity for dependency in process_request.required_dependencies if dependency.data.dependency_type == DependencyType.ASSEMBLY]
        for dependant_entity in process_request.entity.depended_entities:
            if dependant_entity.data.type not in required_assembly_types:
                continue
            dependant_entity.info.log_start_loading(process_request.resource, dependant_entity, self.env.now, process_request.origin_queue)
            yield from process_request.origin_queue.get(dependant_entity.data.ID)
            dependant_entity.current_locatable = process_request.resource
            dependant_entity.info.log_end_loading(process_request.resource, dependant_entity, self.env.now, dependant_entity.current_locatable)

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
        for entity in process_request.get_atomic_entities():
            entity.info.log_start_unloading(process_request.resource, entity, self.env.now, process_request.target_queue)
            yield from process_request.target_queue.put(entity.data)
            entity.info.log_end_unloading(process_request.resource, entity, self.env.now, process_request.target_queue)
        required_assembly_types = [dependency.data.required_entity for dependency in process_request.required_dependencies if dependency.data.dependency_type == DependencyType.ASSEMBLY]
        for dependant_entity in process_request.entity.depended_entities:
            if dependant_entity.data.type not in required_assembly_types:
                continue
            dependant_entity.info.log_start_unloading(process_request.resource, dependant_entity, self.env.now, process_request.target_queue)
            yield from process_request.target_queue.put(dependant_entity.data)
            dependant_entity.info.log_end_unloading(process_request.resource, dependant_entity, self.env.now, process_request.target_queue)
        required_tool_types = [dependency.data.required_entity for dependency in process_request.required_dependencies if dependency.data.dependency_type == DependencyType.TOOL]
        for dependant_entity in process_request.entity.depended_entities:
            if dependant_entity.data.type not in required_tool_types:
                continue
            dependant_entity.current_locatable = process_request.entity.current_locatable
            dependant_entity.info.log_start_unloading(dependant_entity.current_locatable.resource, dependant_entity, self.env.now, dependant_entity.current_locatable)
            yield from dependant_entity.current_locatable.put(dependant_entity.data)
            dependant_entity.info.log_end_unloading(dependant_entity.current_locatable.resource, dependant_entity, self.env.now, dependant_entity.current_locatable)
    
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
        resource: Resource = process_request.get_resource()
        self.resource = resource
        proc = process_request.get_process()
        self.process_model = proc.precedence_graph.create_instance()
        
        entity = process_request.get_entity()
        origin_queue = process_request.origin_queue

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
        for entity in process_request.get_atomic_entities():
            entity.update_location(resource)

        resource.controller.mark_started_process(process_request.capacity_required)
        
        # Execute all processes in the model sequentially on this resource
        # Pick up product from origin queue at the beginning (already done above)
        self.set_next_possible_production_processes()
        while self.next_possible_processes:
            next_process = self.next_possible_processes[0]

            dependency_release_event = None
            dependency_ready_events = []
            router = process_request.entity.router if process_request.entity else None
            resource_dependencies = getattr(resource, "dependencies", [])
            process_dependencies = getattr(next_process, "dependencies", [])
            if router and (resource_dependencies or process_dependencies):
                dependency_release_event = self.env.event()
                dependency_ready_events = router.get_dependencies_for_execution(
                    resource=resource,
                    process=next_process,
                    requesting_item=process_request.requesting_item or process_request.entity,
                    dependency_release_event=dependency_release_event,
                )
            for dependency_ready_event in dependency_ready_events:
                yield dependency_ready_event

            yield from resource.setup(next_process)
            # Get process time
            process_time = next_process.time_model.get_next_time()
            process_state_events = []

            for entity in process_request.get_atomic_entities():
            
                # Wait for a free process slot and get the production state
                production_state: state.State = yield from resource.wait_for_free_process(next_process)
                
                production_state.reserved = True
                # Execute the process
                production_state.state_info.log_product(entity, state.StateTypeEnum.production)
                # Update entity's current process to the process being executed
                entity.current_process = next_process
                production_state.process = self.env.process(production_state.process_state(time=process_time))
                production_state.reserved = False
                process_state_events.append((production_state.process, production_state))
            
            for process_event, production_state in process_state_events:
                yield process_event
                production_state.process = None

            if dependency_release_event and not dependency_release_event.triggered:
                dependency_release_event.succeed()
            
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
        for entity in process_request.get_atomic_entities():
            entity.current_process = proc
        process_request.entity.current_process = proc

        # Release resource capacity requests (must be after marking finished)
        for resource_request in resource_requests:
            resource.release(resource_request)
        
        # Put product back to target queue after all processes are finished
        yield from self.put_entities_of_request(process_request)
        for entity in process_request.get_atomic_entities():
            entity.update_location(process_request.target_queue)

        process_request.entity.router.mark_finished_request(process_request)
        self.resource.controller.mark_finished_process(process_request.capacity_required)
        


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