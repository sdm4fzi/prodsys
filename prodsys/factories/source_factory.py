from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, TYPE_CHECKING

from prodsys.simulation import sim, source
from prodsys.simulation import router as router_module
from prodsys.models.product_data import ProductData
from prodsys.models.source_data import SourceData


if TYPE_CHECKING:
    from prodsys.factories import (
        resource_factory,
        queue_factory,
        time_model_factory,
        sink_factory,
    )
    from prodsys.models import production_system_data


class SourceFactory:
    """
    Factory class that creates and stores `prodsys.simulation` source objects based on the given source data according to `prodsys.models.SourceData`.

    Args:
        env (sim.Environment): prodsys simulation environment.
        product_factory (product_factory.ProductFactory): Factory that creates product objects.
        time_model_factory (time_model_factory.TimeModelFactory): Factory that creates time model objects.
        queue_factory (queue_factory.QueueFactory): Factory that creates queue objects.
        resource_factory (resource_factory.ResourceFactory): Factory that creates resource objects.
        sink_factory (sink_factory.SinkFactory): Factory that creates sink objects.
    """

    def __init__(
        self,
        env: sim.Environment,
        product_factory: product_factory.ProductFactory,
        time_model_factory: time_model_factory.TimeModelFactory,
        queue_factory: queue_factory.QueueFactory,
        resource_factory: resource_factory.ResourceFactory,
        auxiliary_factory: primitive_factory.PrimitiveFactory,
        sink_factory: sink_factory.SinkFactory,
    ):
        self.env = env
        self.product_factory = product_factory
        self.time_model_factory = time_model_factory
        self.queue_factory = queue_factory
        self.resource_factory = resource_factory
        self.auxiliary_factory = auxiliary_factory
        self.sink_factory = sink_factory

        self.sources: Dict[str, source.Source] = {}

    def create_sources(self, adapter: production_system_data.ProductionSystemData):
        """
        Creates source objects based on the given adapter.

        Args:
            adapter (adapter.ProductionSystemAdapter): Adapter that contains the source data.
        """
        for values in adapter.source_data:
            for product_d in adapter.product_data:
                if product_d.product_type == values.product_type:
                    self.add_source(values, product_d)

    def add_source(
        self,
        source_data: SourceData,
        product_data_of_source: ProductData,
    ):
        time_model = self.time_model_factory.get_time_model(source_data.time_model_id)

        source_object = source.Source(
            env=self.env,
            data=source_data,
            product_data=product_data_of_source,
            product_factory=self.product_factory,
            time_model=time_model,
        )
        self.add_queues_to_source(source_object, source_data.output_queues)
        self.sources[source_data.ID] = source_object

    def add_queues_to_source(self, source: source.Source, values: List[str]):
        output_queues = self.queue_factory.get_queues(values)
        source.add_output_queues(output_queues)

    def start_sources(self):
        """
        Starts the processes of all source objects, i.e. initializes the simulation.
        """
        for _source in self.sources.values():
            _source.start_source()

    def get_source(self, ID: str) -> source.Source:
        """
        Returns a source object with the given ID.

        Args:
            ID (str): ID of the source object.

        Returns:
            source.Source: Source object with the given ID.
        """
        if not ID in self.sources:
            raise ValueError(f"Source with ID {ID} not found.")
        return self.sources[ID]

    def get_sources(self, IDs: List[str]) -> List[source.Source]:
        """
        Method returns a list of source objects with the given IDs.

        Args:
            IDs (List[str]): List of IDs that is used to sort the source objects.

        Returns:
            List[source.Source]: List of source objects with the given IDs.
        """
        sources = []
        for ID in IDs:
            if ID in self.sources:
                sources.append(self.sources[ID])
            else:
                raise ValueError(f"Source with ID {ID} not found.")
        return sources

    def get_sources_with_product_type(self, __product_type: str) -> List[source.Source]:
        """
        Method returns a list of source objects with the given product type.

        Args:
            __product_type (str): Product type that is used to sort the source objects.

        Returns:
            List[source.Source]: List of source objects with the given product type.
        """
        return [
            s for s in self.sources.values() if __product_type == s.data.product_type
        ]


from prodsys.factories import (
    primitive_factory,
    product_factory,
    resource_factory,
    queue_factory,
    time_model_factory,
    sink_factory,
)
