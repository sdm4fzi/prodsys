from __future__ import annotations

from typing import List, TYPE_CHECKING, Tuple, Generator

from simpy import events

import logging

logger = logging.getLogger(__name__)

from prodsys.simulation import sim, store, time_model
from prodsys.simulation import router as router_module
from prodsys.models import source_data, product_data


class Source:
    """
    Class that represents a source.

    Args:
        env (sim.Environment): The simulation environment.
        data (source_data.SourceData): The source data.
        product_data (product_data.ProductData): The product data of the products to be created.
        product_factory (product_factory.ProductFactory): The product factory.
        time_model (time_model.TimeModel): The time model of the source.
        router (router.Router): The router of the created products.
        output_queues (List[store.Queue], optional): The output queues. Defaults to [].
    """

    def __init__(
        self,
        env: sim.Environment,
        data: source_data.SourceData,
        product_data: product_data.ProductData,
        product_factory: product_factory.ProductFactory,
        time_model: time_model.TimeModel,
    ):
        self.env = env
        self.data = data
        self.product_data = product_data
        self.product_factory = product_factory
        self.time_model = time_model
        self.router: router_module.Router = None
        self.output_queues: List[store.Queue] = []

    def add_output_queues(self, output_queues: List[store.Queue]):
        """
        Adds output queues to the source.

        Args:
            output_queues (List[store.Queue]): The output queues.
        """
        self.output_queues.extend(output_queues)

    def start_source(self):
        """
        Starts the source simpy process.
        """
        self.env.process(self.create_product_loop())

    def get_output_queue_length(self) -> int:
        """
        Returns total number of items in all output_queues.

        Returns:
            int: Sum of items in the source output-queues.
        """
        return sum([len(q.items) for q in self.output_queues])

    def get_input_queue_length(self) -> int:
        """
        Returns total number of items in all input_queues.

        Returns:
            int(0)
        """
        return 0

    def create_product_loop(self) -> Generator:
        """
        Simpy process that creates products and puts them in the output queues.

        Yields:
            Generator: Yields when a product is created or when a product is put in an output queue.
        """
        while True:
            inter_arrival_time = self.time_model.get_next_time()
            if inter_arrival_time <= 0:
                break
            yield self.env.timeout(inter_arrival_time)
            product = self.product_factory.create_product(
                self.product_data, self.data.routing_heuristic
            )
            for queue in self.output_queues:
                queue.reserve()
                yield from queue.put(product.data)
            product.update_location(self)
            product.process = self.env.process(product.process_product())

    def get_location(self) -> List[float]:
        """
        Returns the location of the source.

        Returns:
            List[float]: The location. Has to be a list of length 2.
        """
        return self.data.location


from prodsys.factories import product_factory

# Source.model_rebuild()
