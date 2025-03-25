from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field


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
    from prodsys.adapters import adapter


class SourceFactory(BaseModel):
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

    env: sim.Environment
    product_factory: product_factory.ProductFactory
    time_model_factory: time_model_factory.TimeModelFactory
    queue_factory: queue_factory.QueueFactory
    resource_factory: resource_factory.ResourceFactory
    auxiliary_factory: auxiliary_factory.AuxiliaryFactory
    sink_factory: sink_factory.SinkFactory

    product_data: List[ProductData] = Field(default_factory=list, init=False)
    sources: List[source.Source] = Field(default_factory=list, init=False)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def create_sources(self, adapter: adapter.ProductionSystemAdapter):
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
        self.sources.append(source_object)

    def add_queues_to_source(self, source: source.Source, values: List[str]):
        output_queues = self.queue_factory.get_queues(values)
        source.add_output_queues(output_queues)

    def start_sources(self):
        """
        Starts the processes of all source objects, i.e. initializes the simulation.
        """
        for _source in self.sources:
            _source.start_source()

    def get_source(self, ID: str) -> source.Source:
        """
        Returns a source object with the given ID.

        Args:
            ID (str): ID of the source object.

        Returns:
            source.Source: Source object with the given ID.
        """
        return [s for s in self.sources if s.data.ID == ID].pop()

    def get_sources(self, IDs: List[str]) -> List[source.Source]:
        """
        Method returns a list of source objects with the given IDs.

        Args:
            IDs (List[str]): List of IDs that is used to sort the source objects.

        Returns:
            List[source.Source]: List of source objects with the given IDs.
        """
        return [s for s in self.sources if s.data.ID in IDs]

    def get_sources_with_product_type(self, __product_type: str) -> List[source.Source]:
        """
        Method returns a list of source objects with the given product type.

        Args:
            __product_type (str): Product type that is used to sort the source objects.

        Returns:
            List[source.Source]: List of source objects with the given product type.
        """
        return [s for s in self.sources if __product_type == s.data.product_type]


from prodsys.factories import (
    product_factory,
    resource_factory,
    queue_factory,
    time_model_factory,
    auxiliary_factory,
    sink_factory,
)
