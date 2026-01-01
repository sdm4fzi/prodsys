from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING, Union

from prodsys.simulation import sim, source
from prodsys.simulation.order_source import OrderSource
from prodsys.simulation import router as router_module
from prodsys.models.product_data import ProductData
from prodsys.models.source_data import SourceData, OrderSourceData
from prodsys.models import performance_data, order_data


if TYPE_CHECKING:
    from prodsys.factories import (
        resource_factory,
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
        queue_factory: port_factory.QueueFactory,
        resource_factory: resource_factory.ResourceFactory,
        sink_factory: sink_factory.SinkFactory,
        conwip: Optional[int] = None,
        schedule: Optional[List[performance_data.Event]] = None,
    ):
        self.env = env
        self.product_factory = product_factory
        self.time_model_factory = time_model_factory
        self.queue_factory = queue_factory
        self.resource_factory = resource_factory
        self.sink_factory = sink_factory
        self.conwip = conwip
        self.schedule_per_product = self._schedule_per_product(schedule)

        self.sources: Dict[str, source.Source] = {}


    def _get_product_type(self, product_id: str) -> str:
        return product_id.split("_")[0]

    def _schedule_per_product(self, schedule: Optional[List[performance_data.Event]]) -> Optional[Dict[str, List[performance_data.Event]]]:
        schedule_per_product = {}
        if not schedule:
            return schedule_per_product

        for event in schedule:
            product_type = self._get_product_type(event.product)
            if product_type not in schedule_per_product:
                schedule_per_product[product_type] = []
            schedule_per_product[product_type].append(event)
        return schedule_per_product

    def create_sources(self, adapter: production_system_data.ProductionSystemData):
        """
        Creates source objects based on the given adapter.

        Args:
            adapter (adapter.ProductionSystemAdapter): Adapter that contains the source data.
        """
        for values in adapter.source_data:
            if isinstance(values, OrderSourceData):
                # Handle OrderSource
                if adapter.order_data:
                    # Filter orders that belong to this order source
                    relevant_orders = [
                        order for order in adapter.order_data
                        if order.ID in values.order_ids
                    ]
                    if relevant_orders:
                        self.add_order_source(values, relevant_orders, adapter)
            else:
                # Handle regular Source
                for product_d in adapter.product_data:
                    if product_d.type == values.product_type:
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
            conwip=self.conwip,
            schedule=self.schedule_per_product.get(product_data_of_source.type, None),
        )
        self.add_ports_to_source(source_object, source_data.ports)
        self.sources[source_data.ID] = source_object

    def add_ports_to_source(self, source: source.Source, values: List[str]):
        ports = self.queue_factory.get_queues(values)
        source.add_ports(ports)

    def add_order_source(
        self,
        order_source_data: OrderSourceData,
        orders: List[order_data.OrderData],
        adapter: production_system_data.ProductionSystemData,
    ):
        """
        Adds an order source to the factory.

        Args:
            order_source_data (OrderSourceData): The order source data.
            orders (List[OrderData]): List of orders for this source.
            adapter (ProductionSystemData): The production system data adapter.
        """
        # Create mapping from product type to ProductData
        product_type_to_data: Dict[str, ProductData] = {}
        for order in orders:
            for ordered_product in order.ordered_products:
                product_type = ordered_product.product_type
                if product_type not in product_type_to_data:
                    # Find ProductData for this product type
                    for product_d in adapter.product_data:
                        if product_d.type == product_type:
                            product_type_to_data[product_type] = product_d
                            break
        
        order_source_object = OrderSource(
            env=self.env,
            data=order_source_data,
            product_factory=self.product_factory,
            orders=orders,
            conwip=self.conwip,
        )
        order_source_object.set_product_type_mapping(product_type_to_data)
        self.add_ports_to_source(order_source_object, order_source_data.ports)
        self.sources[order_source_data.ID] = order_source_object

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
        if ID in self.sources:
            return self.sources[ID]
        raise ValueError(f"Source with ID {ID} not found.")

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
        from prodsys.simulation.order_source import OrderSource
        regular_sources = [
            s for s in self.sources.values() 
            if hasattr(s.data, 'product_type') and __product_type == s.data.product_type
        ]
        # Check order sources for this product type
        order_sources_with_type = []
        for src in self.sources.values():
            if isinstance(src, OrderSource):
                # Check if any order in this order source has the product type
                for order in src.orders:
                    for ordered_product in order.ordered_products:
                        if ordered_product.product_type == __product_type:
                            order_sources_with_type.append(src)
                            break
                    if src in order_sources_with_type:
                        break
        return regular_sources + order_sources_with_type


from prodsys.factories import (
    port_factory,
    primitive_factory,
    product_factory,
    resource_factory,
    time_model_factory,
    sink_factory,
)
