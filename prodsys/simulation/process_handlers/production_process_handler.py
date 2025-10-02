from __future__ import annotations

from typing import Generator, TYPE_CHECKING, Optional
import numpy as np

import logging

from prodsys.simulation import (
    port,
    sim,
    state,
    process,
)

from prodsys.simulation.process import (
    ReworkProcess,
)

if TYPE_CHECKING:
    from prodsys.simulation import (
        product,
        process,
        state,
    )
    from prodsys.simulation import request as request_module


logger = logging.getLogger(__name__)


class ProductionProcessHandler:
    """
    A production controller is responsible for controlling the processes of a production resource. The controller is requested by products requiring processes. The controller decides has a control policy that determines with which sequence requests are processed.
    """

    def __init__(self, env: sim.Environment) -> None:
        self.env = env
        self.resource = None
        self.process_time: Optional[float] = None

    def set_process_time(self, process_time: float) -> None:
        """
        Set the process time for the production process.

        Args:
            process_time (float): The process time for the production process.
        """
        self.process_time = process_time

    def get_next_product_for_process(
        self, queue: port.Queue, product: product.Product
    ) -> Generator:
        """
        Get the next product for a process. The product is removed (get) from the input queues of the resource.

        Args:
            resource (resources.Resource): The resource to take the product from.
            product (product.Product): The product that is requesting the product.

        Returns:
            List[events.Event]: The event that is triggered when the product is taken from the queue (multiple events for multiple products, e.g. for a batch process or an assembly).
        """
        yield from queue.get(product.data.ID)

    def put_product_to_output_queue(
        self, queue: port.Queue, product: product.Product
    ) -> Generator:
        """
        Place a product to the output queue (put) of the resource.

        Args:
            resource (resources.Resource): The resource to place the product to.
            products (List[product.Product]): The products to be placed.

        Returns:
            List[events.Event]: The event that is triggered when the product is placed in the queue (multiple events for multiple products, e.g. for a batch process or an assembly).
        """
        yield from queue.put(product.data)

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
        product = process_request.get_item()

        origin_queue, target_queue = (
            process_request.origin_queue,
            process_request.target_queue,
        )
        if process_request.required_dependencies:
            yield process_request.request_dependencies()
        yield from resource.setup(process)
        with resource.request() as req:
            yield req
            self.get_next_product_for_process(origin_queue, product)
            resource.controller.mark_started_process()
            production_state: state.State = yield from resource.wait_for_free_process(
                process
            )
            production_state.reserved = True
            yield from self.run_process(production_state, product, process)
            production_state.process = None

            yield from self.put_product_to_output_queue(target_queue, product)
            product.update_location(target_queue)
            
            buffer_placement_event = product.router.request_buffering(process_request)
            if buffer_placement_event:
                yield buffer_placement_event
            product.router.mark_finished_request(process_request)
            self.resource.controller.mark_finished_process()

    def run_process(
        self,
        input_state: state.State,
        target_product: product.Product,
        process: process.Process,
    ):
        """
        Run the process of a product. The process is started and the product is logged.

        Args:
            input_state (state.State): The production state of the process.
            target_product (product.Product): The product that is processed.
        """
        input_state.state_info.log_product(
            target_product, state.StateTypeEnum.production
        )
        input_state.process = self.env.process(input_state.process_state(time=self.process_time))  # type: ignore False
        input_state.reserved = False
        self.handle_rework_required(target_product, process)

        yield input_state.process

    def handle_rework_required(
        self, product: product.Product, process: process.Process
    ):
        """
        Determine if rework is needed based on the process's failure rate.

        Args:
            process (process.Process): The process to check for failure rate.
        """
        if isinstance(process, ReworkProcess):
            return
        failure_rate = process.data.failure_rate
        if not failure_rate or failure_rate == 0:
            return
        rework_needed = np.random.choice(
            [True, False], p=[failure_rate, 1 - failure_rate]
        )
        if not rework_needed:
            return
        product.add_needed_rework(process)

