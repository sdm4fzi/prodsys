from __future__ import annotations

from typing import Generator, TYPE_CHECKING

import logging

from prodsys.simulation import (
    sim,
    state,
    process,
)
from prodsys.models.dependency_data import DependencyType
from prodsys.simulation.entities.entity import EntityType
from prodsys.simulation import standby_logging
from prodsys.simulation import port as port_module

if TYPE_CHECKING:
    from prodsys.simulation import (
        process,
        state,
    )
    from prodsys.simulation import request as request_module
    from prodsys.simulation.entities import product


logger = logging.getLogger(__name__)


def get_process_time_for_lots(
        request: request_module.Request
) -> float:
    """
    Get the expected process time for a batch of requests.

    Args:
        request (request_module.Request): The request to get the process time for.

    Returns:
        float: The expected process time for the batch.
    """
    if not request.process:
        raise ValueError("Request has no process.")
    return request.process.time_model.get_next_time(
    )


class ProductionProcessHandler:
    """
    A production controller is responsible for controlling the processes of a production resource. The controller is requested by products requiring processes. The controller decides has a control policy that determines with which sequence requests are processed.
    """

    def __init__(self, env: sim.Environment) -> None:
        self.env = env
        self.resource = None

    def get_entities_of_request(
        self, process_request: request_module.Request
    ) -> Generator:
        """
        Get the next product for a process. The product is removed (get) from the input queues of the resource.

        Args:
            process_request (request_module.Request): The request to get the entities from.

        Returns:
            Generator: The generator yields when the product is taken from the queue (multiple events for multiple products, e.g. for a batch process or an assembly).
        """
        for entity in process_request.get_atomic_entities():
            entity.info.log_start_loading(process_request.resource, entity, self.env.now, process_request.origin_queue)
            yield from standby_logging.log_starved_around_get(
                process_request.resource, process_request.origin_queue, entity.data.ID
            )
            entity.info.log_end_loading(process_request.resource, entity, self.env.now, process_request.origin_queue)
        required_primitive_types = [dependency.data.required_entity for dependency in process_request.required_dependencies if dependency.data.dependency_type == DependencyType.TOOL or dependency.data.dependency_type == DependencyType.ASSEMBLY]
        for dependant_entity in process_request.entity.depended_entities:
            if dependant_entity.data.type not in required_primitive_types:
                continue
            dependant_entity.info.log_start_loading(process_request.resource, dependant_entity, self.env.now, process_request.origin_queue)
            locatable = dependant_entity.current_locatable
            if isinstance(locatable, port_module.Queue):
                yield from standby_logging.log_starved_around_get(
                    process_request.resource, locatable, dependant_entity.data.ID
                )
            else:
                yield from locatable.get(dependant_entity.data.ID)
            dependant_entity.update_location(process_request.resource)
            dependant_entity.info.log_end_loading(process_request.resource, dependant_entity, self.env.now, dependant_entity.current_locatable)

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
        for entity in process_request.get_atomic_entities():
            entity.info.log_start_unloading(process_request.resource, entity, self.env.now, process_request.target_queue)
            yield from standby_logging.log_blocked_around_put(
                process_request.resource, process_request.target_queue, entity.data
            )
            entity.info.log_end_unloading(process_request.resource, entity, self.env.now, process_request.target_queue)
        required_assembly_types = [dependency.data.required_entity for dependency in process_request.required_dependencies if dependency.data.dependency_type == DependencyType.ASSEMBLY]
        for dependant_entity in process_request.entity.depended_entities:
            if dependant_entity.data.type not in required_assembly_types:
                continue    
            dependant_entity.info.log_consumption(process_request.resource, dependant_entity, self.env.now)
        required_tool_types = [dependency.data.required_entity for dependency in process_request.required_dependencies if dependency.data.dependency_type == DependencyType.TOOL]
        for dependant_entity in process_request.entity.depended_entities:
            if dependant_entity.data.type not in required_tool_types:
                continue
            dependant_entity.current_locatable = process_request.entity._current_locatable
            dependant_entity.info.log_start_unloading(dependant_entity.current_locatable.resource, dependant_entity, self.env.now, dependant_entity.current_locatable)
            locatable = dependant_entity.current_locatable
            if isinstance(locatable, port_module.Queue):
                yield from standby_logging.log_blocked_around_put(
                    process_request.resource, locatable, dependant_entity.data
                )
            else:
                yield from locatable.put(dependant_entity.data)
            dependant_entity.info.log_end_unloading(dependant_entity.current_locatable.resource, dependant_entity, self.env.now, dependant_entity.current_locatable)

    def handle_request(self, process_request: request_module.Request) -> Generator:
        """
        Start the next process with the following logic:

        1. Setup the resource for the process.
        2. Wait until the resource is free for the process.
        3. Retrieve the product from the queue.
        4. Run the process and wait until finished.
        5. Place the product in the output queue.

        Yields:
            Generator: The generator yields when the process is finished.
        """
        resource = process_request.get_resource()
        self.resource = resource
        process = process_request.get_process()

        # Take only dependencies of the main request of the lot
        if process_request.required_dependencies:
            yield process_request.request_dependencies()
        yield from resource.setup(process)
        resource_requests = []
        for _ in range(process_request.capacity_required):
            resource_request = resource.request()
            yield resource_request
            resource_requests.append(resource_request)
        

            
        # Now get all entities
        yield from self.get_entities_of_request(process_request)

        process_time = get_process_time_for_lots(process_request)
        resource.controller.mark_started_process(process_request.capacity_required)
        process_state_events = []
        for entity in process_request.get_atomic_entities():
            entity.update_location(process_request.resource)
            production_state: state.State = yield from resource.wait_for_free_process(
                process
            )
            production_state.reserved = True
            process_event = self.env.process(self.run_process(production_state,entity, process, process_time))
            process_state_events.append((process_event, production_state))
        for process_event, production_state in process_state_events:
            yield process_event
            # Store failure status on entity if available
            if hasattr(production_state.state_info, '_process_ok'):
                for entity in process_request.get_atomic_entities():
                    entity.last_process_failed = not production_state.state_info._process_ok
            production_state.process = None

        # Release worker / resource dependencies (e.g. ``dep_..._worker``)
        # AS SOON AS the processing time has elapsed.  Holding them through
        # the unload phase — the legacy behaviour — pins the worker to the
        # station whenever the output queue is full, which produced the
        # cascade-fill deadlock observed on the SICK 288-order workload at
        # ~13 h sim time (paPreAssembly02_output / paSwing_input go 34/34,
        # the manual-step worker on Workers_Part1 stays stuck on the
        # ``dep_JobPreAssembly__VFS_Prog_worker`` start state, no further
        # transports happen and the simulator wedges).  Mirrors the
        # ProcessModel handler which already triggers the same event right
        # after its per-step processing completes.
        if (
            process_request.processing_finished is not None
            and not process_request.processing_finished.triggered
        ):
            process_request.processing_finished.succeed()

        for resource_request in resource_requests:
            resource.release(resource_request)
        yield from self.put_entities_of_request(process_request)
        process_request.entity.update_location(process_request.target_queue)

        if process_request.entity.type == EntityType.LOT:
            process_request.entity.clear()

        buffer_placement_events = []
        for entity in process_request.get_atomic_entities():
            buffer_placement_event = entity.router.request_buffering(process_request)
            if buffer_placement_event:
                buffer_placement_events.append(buffer_placement_event)
        for buffer_placement_event in buffer_placement_events:
            yield buffer_placement_event

        self.resource.controller.mark_finished_process(process_request.capacity_required)
        process_request.entity.router.mark_finished_request(process_request)

    def run_process(
        self,
        input_state: state.State,
        target_product: product.Product,
        process: process.Process,
        process_time: float,
    ) -> Generator:
        """
        Run the process of a product. The process is started and the product is logged.

        Args:
            input_state (state.State): The production state of the process.
            target_product (product.Product): The product that is processed.
            process (process.Process): The process to run.
            process_time (float): The process time.
        """
        input_state.state_info.log_product(
            target_product, state.StateTypeEnum.production
        )
        input_state.process = self.env.process(input_state.process_state(time=process_time))  # type: ignore False
        input_state.reserved = False

        yield input_state.process
