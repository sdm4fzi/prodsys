
from __future__ import annotations

from typing import Generator, TYPE_CHECKING, Optional

import logging

from prodsys.simulation import (
    sim,
    state,
    process,
)

if TYPE_CHECKING:
    from prodsys.simulation import (
        product,
        process,
        state,
        resources,
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
        self.process_time: Optional[float] = None

    def set_process_time(self, process_time: float) -> None:
        """
        Set the process time for the process model.

        Args:
            process_time (float): The process time for the process model.
        """
        self.process_time = process_time

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
        process_model = process_request.get_process()
        product = process_request.get_item()

        # Get the process model from the product
        if hasattr(product.process_model, 'get_next_possible_processes'):
            current_model = product.process_model
        else:
            # Create a new process model instance from the process model data
            from prodsys.simulation import process_models
            if isinstance(process_model.data, process.ProcessModelData):
                # Create a PrecedenceGraphProcessModel for complex DAGs
                current_model = process_models.PrecedenceGraphProcessModel()
                # TODO: Initialize the process model with the contained processes
                # This would require the process factory to create the individual processes
            else:
                # Create a ListProcessModel for sequential processes
                current_model = process_models.ListProcessModel([])

        with resource.request() as req:
            yield req
            resource.controller.mark_started_process()

            # Execute processes according to the process model
            while True:
                next_processes = current_model.get_next_possible_processes()
                if not next_processes:
                    break

                # For now, execute the first available process
                # In a more sophisticated implementation, this could use scheduling algorithms
                # TODO: make this smarter with a control policy
                chosen_process = next_processes[0]

                # Find the matching actual process in the resource
                actual_process = None
                for res_process in resource.processes:
                    if res_process.data.ID == chosen_process.data.ID:
                        actual_process = res_process
                        break

                if actual_process:
                    # Execute the individual process
                    yield from self.execute_individual_process(
                        actual_process, product, resource, process_request
                    )

                # Update the process model marking
                current_model.update_marking_from_transition(chosen_process)

            resource.controller.mark_finished_process()

    def execute_individual_process(
        self,
        process: process.PROCESS_UNION,
        product: product.Product,
        resource: resources.Resource,
        process_request: request_module.Request,
    ) -> Generator:
        """
        Execute an individual process within the process model.

        Args:
            process (process.PROCESS_UNION): The individual process to execute.
            product (product.Product): The product being processed.
            resource (resources.Resource): The resource executing the process.
            process_request (request_module.Request): The original process request.

        Yields:
            Generator: The generator yields when the individual process is finished.
        """
        # TODO: use here the router of the system or the product to route the item for processing.
        origin_queue, target_queue = (
            process_request.origin_queue,
            process_request.target_queue,
        )

        # Setup the process
        yield from resource.setup(process)

        # Wait for the process to be available
        process_state: state.State = yield self.env.process(
            resource.wait_for_free_process(process)
        )
        process_state.reserved = True

        # Execute the process
        process_state.process = self.env.process(
            process_state.process_state()
        )
        yield process_state.process
        process_state.process = None

