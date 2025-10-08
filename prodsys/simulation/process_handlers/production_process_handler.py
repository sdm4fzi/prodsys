from __future__ import annotations

from typing import Generator, TYPE_CHECKING
import numpy as np

import logging

from prodsys.simulation import (
    sim,
    state,
    process,
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
            yield from process_request.origin_queue.get(entity.data.ID)

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
            yield from process_request.target_queue.put(entity.data)

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
            production_state.process = None

        yield from self.put_entities_of_request(process_request)
        for entity in process_request.get_atomic_entities():
            entity.update_location(process_request.target_queue)

        buffer_placement_events = []
        for entity in process_request.get_atomic_entities():
            buffer_placement_event = entity.router.request_buffering(process_request)
            if buffer_placement_event:
                buffer_placement_events.append(buffer_placement_event)
        for buffer_placement_event in buffer_placement_events:
            yield buffer_placement_event

        for entity in process_request.get_atomic_entities():
            entity.router.mark_finished_request(process_request)
        self.resource.controller.mark_finished_process(process_request.capacity_required)
        for resource_request in resource_requests:
            resource.release(resource_request)

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
