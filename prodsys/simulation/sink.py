from __future__ import annotations

from typing import List, TYPE_CHECKING

from prodsys.simulation import sim, store
from prodsys.models import sink_data

if TYPE_CHECKING:
    from prodsys.simulation import product


class Sink:
    """
    Class that represents a sink.

    Args:
        env (sim.Environment): The simulation environment.
        data (sink_data.SinkData): The sink data.
        product_factory (product_factory.ProductFactory): The product factory.
        input_queues (List[store.Queue], optional): The input queues. Defaults to [].
    """

    def __init__(
        self,
        env: sim.Environment,
        data: sink_data.SinkData,
        product_factory: product_factory.ProductFactory,
    ):
        self.env = env
        self.data = data
        self.product_factory = product_factory
        self.input_queues: List[store.Queue] = []

    def add_input_queues(self, input_queues: List[store.Queue]):
        """
        Adds input queues to the sink.

        Args:
            input_queues (List[store.Queue]): The input queues.
        """
        self.input_queues.extend(input_queues)

    def get_location(self) -> List[float]:
        """
        Returns the location of the sink.

        Returns:
            List[float]: The location. Has to be a list of length 2.
        """
        return self.data.location

    def get_input_queue_length(self) -> int:
        """
        Returns total number of items in all input_queues. Defaults to 0 for a sink.

        Returns:
            int(0)
        """
        return 0

    def get_output_queue_length(self) -> int:
        """
        Returns zero. Needed for transport control policies that use the target locations output queue for request ordering.
        Returns:
            int(0)
        """
        return 0

    def register_finished_product(self, product: product.Product):
        """
        Registers a finished product when it reaches the sink.

        Args:
            product (product.Product): The finished product.
        """
        self.product_factory.register_finished_product(product)


from prodsys.factories import product_factory
