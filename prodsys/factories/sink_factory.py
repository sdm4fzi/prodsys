from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from prodsys.simulation import sim, sink
from prodsys.models import sink_data

if TYPE_CHECKING:
    from prodsys.factories import product_factory, queue_factory
    from prodsys.adapters import adapter


class SinkFactory(BaseModel):
    """
    Factory class that creates and stores `prodsys.simulation` sink objects from `prodsys.models` sink objects.

    Args:
        env (sim.Environment): prodsys simulation environment.
        product_factory (product_factory.ProductFactory): Factory that creates product objects.
        queue_factory (queue_factory.QueueFactory): Factory that creates queue objects.
    """

    env: sim.Environment
    product_factory: product_factory.ProductFactory
    queue_factory: queue_factory.QueueFactory

    sinks: List[sink.Sink] = Field(default_factory=list, init=False)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def create_sinks(self, adapter: adapter.ProductionSystemAdapter):
        """
        Creates sink objects based on the given adapter.

        Args:
            adapter (adapter.ProductionSystemAdapter): Adapter that contains the sink data.
        """
        for data in adapter.sink_data:
            self.add_sink(data)

    def add_sink(self, sink_data: sink_data.SinkData):
        values = {
            "env": self.env,
            "data": sink_data,
            "product_factory": self.product_factory,
        }
        sink_object = TypeAdapter(sink.Sink).validate_python(values)
        self.add_queues_to_sink(sink_object)
        self.sinks.append(sink_object)

    def add_queues_to_sink(self, _sink: sink.Sink):
        input_queues = self.queue_factory.get_queues(_sink.data.input_queues)
        _sink.add_input_queues(input_queues)

    def get_sink(self, ID: str) -> sink.Sink:
        """
        Method returns a sink object with the given ID.

        Args:
            ID (str): ID of the sink object.
        Returns:
            sink.Sink: Sink object with the given ID.
        """
        return [s for s in self.sinks if s.data.ID == ID].pop()

    def get_sinks(self, IDs: List[str]) -> List[sink.Sink]:
        """
        Method returns a list of sink objects with the given IDs.

        Args:
            IDs (List[str]): List of IDs that is used to sort the sink objects.

        Returns:
            List[sink.Sink]: List of sink objects with the given IDs.
        """
        return [s for s in self.sinks if s.data.ID in IDs]

    def get_sinks_with_product_type(self, __product_type: str) -> List[sink.Sink]:
        """
        Method returns a list of sink objects with the given product type.

        Args:
            __product_type (str): Product type that is used to sort the sink objects.

        Returns:
            List[sink.Sink]: List of sink objects with the given product type.
        """
        return [s for s in self.sinks if __product_type == s.data.product_type]


from prodsys.factories import product_factory, queue_factory
