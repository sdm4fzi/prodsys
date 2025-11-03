from __future__ import annotations

from typing import List, TYPE_CHECKING, Literal

from prodsys.simulation import port, sim
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
        self.ports: List[port.Queue] = []
        self.can_move = False

    def add_ports(self, ports: List[port.Queue]):
        """
        Adds input queues to the sink.

        Args:
            ports (List[store.Queue]): The input ports.
        """
        self.ports.extend(ports)

    def get_location(self, interaction: Literal["input"] = "input") -> List[float]:
        # FIXME: updat this location here!
        if interaction == "out":
            raise ValueError(
                "Sink does not have an output location. Use 'input' instead."
            )
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
        
        if(product.data.becomes_primitive):
            router = self.product_factory.router
            
            self.product_factory.router.primitive_factory.primitives.append(product)
            
            if self.product_factory.router:
                if product.data.type not in router.free_entities_by_type:
                    router.free_entities_by_type[product.data.type] = []
                router.free_entities_by_type[product.data.type].append(product)
                if not router.got_primitive_request.triggered:
                    router.got_primitive_request.succeed() 
        
        self.product_factory.register_finished_product(product)


from prodsys.factories import product_factory
