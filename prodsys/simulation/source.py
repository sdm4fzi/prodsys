from __future__ import annotations

from typing import List, TYPE_CHECKING, Literal, Optional, Set, Tuple, Generator

from simpy import events

import logging


from prodsys.simulation import port, sim, time_model
from prodsys.simulation import router as router_module
from prodsys.models import source_data, product_data, performance_data

from prodsys.simulation import product_processor

if TYPE_CHECKING:
    from prodsys.factories import product_factory

logger = logging.getLogger(__name__)


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
        conwip: Optional[int] = None,
        schedule: Optional[List[performance_data.Event]] = None,
    ):
        self.env = env
        self.data = data
        self.product_data = product_data
        self.product_factory = product_factory
        self.time_model = time_model
        self.conwip = conwip
        self.schedule = schedule
        self.release_index = 0
        self.released_product_ids: Set[str] = set()
        self.ports: List[port.Queue] = []
        self.can_move = False
        self.product_processor = product_processor.ProductProcessor(env)

    def add_ports(self, ports: List[port.Queue]):
        """
        Adds output queues to the source.

        Args:
            ports (List[store.Queue]): The source ports.
        """
        self.ports.extend(ports)

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
        return sum([len(q.items) for q in self.ports])

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
            if self.schedule:
                if self.release_index >= len(self.schedule):
                    return
                if self.schedule[self.release_index].product in self.released_product_ids:
                    self.release_index += 1
                    continue
                inter_arrival_time = self.schedule[self.release_index].time - self.env.now
                if inter_arrival_time <= 0:
                    inter_arrival_time = 1
            else:
                inter_arrival_time = self.time_model.get_next_time()
                if inter_arrival_time <= 0:
                    break
            yield self.env.timeout(inter_arrival_time)
            if self.conwip is not None and len(self.product_factory.products.values()) >= self.conwip:
                print(f"Source {self.data.ID} has reached conwip {self.conwip}, waiting for next product")
                continue
            print("creating product")
            if self.schedule:
                product_index = int(self.schedule[self.release_index].product.split("_")[-1])
                self.released_product_ids.add(self.schedule[self.release_index].product)
                # Temporarily override the product_counter to use the scheduled product index
                saved_counter = self.product_factory.product_counter
                self.product_factory.product_counter = product_index
                product = self.product_factory.create_product(
                    self.product_data, self.data.routing_heuristic
                )
                # Don't restore counter - let it continue from here
            else:
                product = self.product_factory.create_product(
                    self.product_data, self.data.routing_heuristic
                )
            # TODO: this logic should be moved to the interaction handler!
            for queue in self.ports:
                queue.reserve()
                yield from queue.put(product.data)
                product.update_location(queue)
            self.env.process(self.product_processor.process_product(product))
            self.release_index += 1

    def get_location(self) -> List[float]:
        return self.data.location
