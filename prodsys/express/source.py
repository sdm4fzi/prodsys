from __future__ import annotations

from typing import List, Optional
from uuid import uuid1

from pydantic import Field
from pydantic.dataclasses import dataclass

from prodsys.express import core, time_model, port
from prodsys.express.order import Order
from prodsys.express.product import Product

from prodsys.models import source_data
import prodsys
import prodsys.models
from prodsys.models.core_asset import Location2D
import prodsys.models.production_system_data


@dataclass
class Source(core.ExpressObject):
    """
    Class that represents a source.

    Args:
        product (product.Product): Product of the source.
        time_model (time_model.TIME_MODEL_UNION): Time model of the source that determines the inter-arrival time of products.
        location (conlist(float, min_length=2, max_length=2)): Location of the source.
        routing_heuristic (source_data.RoutingHeuristic, optional): Routing heuristic of the source. Defaults to source_data.RoutingHeuristic.random.
        ID (str): ID of the source.

    Attributes:
        _output_queues (List[queue_data.QueueData]): Output queues of the source.

    Examples:
        Creation of a source with a product, a time model and a location:
        ```py
        import prodsys.express as psx
        welding_time_model = psx.time_model_data.FunctionTimeModel(
            distribution_function="normal",
            location=20.0,
            scale=5.0,
        )
        welding_process_1 = psx.process.ProductionProcess(
            time_model=welding_time_model,
        )
        welding_process_2 = psx.process.ProductionProcess(
            time_model=welding_time_model,
        )
        transport_time_model = psx.time_model_data.ManhattenDistanceTimeModel(
            speed=10,
            reaction_time= 0.3
        )
        transport_process = psx.process.TransportProcess(
            time_model=transport_time_model,
        )
        product = psx.Product(
            processes=[welding_process_1, welding_process_2],
            transport_process=transport_process
        )
        arrival_time_model = psx.time_model_data.FunctionTimeModel(
            distribution_function="exponential",
            scale=10.0,
        )
        psx.Source(
            product=product,
            time_model=arrival_time_model,
            location=[0.0, 0.0],
        )
        ```
    """

    product: Product
    time_model: time_model.TIME_MODEL_UNION
    location: Location2D
    routing_heuristic: source_data.RoutingHeuristic = (
        source_data.RoutingHeuristic.random
    )
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    ports: List[port.Queue] = Field(default_factory=list, init=False)

    def to_model(self) -> source_data.SourceData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            source_data.SourceData: An instance of the data object.
        """
        source = source_data.SourceData(
            ID=self.ID,
            description="",
            location=self.location,
            product_type=self.product.ID,
            time_model_id=self.time_model.ID,
            routing_heuristic=self.routing_heuristic,
        )
        if not self.ports:
            port_data = [
                prodsys.models.production_system_data.get_default_queue_for_source(source)
            ]
            self.ports = [port.Queue(ID=q.ID, capacity=q.capacity, location=q.location, interface_type=q.interface_type) for q in port_data]
        source.ports = [q.ID for q in self.ports]
        return source




@dataclass
class OrderSource(core.ExpressObject):
    """
    Class that represents an order source that releases products based on orders.

    Args:
        orders (List[Order]): List of orders that this source should release.
        location (conlist(float, min_length=2, max_length=2)): Location of the order source.
        routing_heuristic (source_data.RoutingHeuristic, optional): Routing heuristic of the source. Defaults to source_data.RoutingHeuristic.random.
        ID (str): ID of the order source.

    Attributes:
        ports (List[queue_data.QueueData]): Output queues of the order source.

    Examples:
        Creation of an order source with orders:
        ```py
        import prodsys.express as psx
        
        # Create orders
        order1 = psx.Order(
            ID="Order_1",
            ordered_products=[psx.OrderedProduct(product_type="Product_1", quantity=2)],
            order_time=0.0,
            release_time=10.0,
            priority=1
        )
        order2 = psx.Order(
            ID="Order_2",
            ordered_products=[psx.OrderedProduct(product_type="Product_2", quantity=1)],
            order_time=5.0,
            release_time=15.0,
            priority=1
        )
        
        psx.OrderSource(
            orders=[order1, order2],
            location=[0.0, 0.0],
        )
        ```
    """

    orders: List[Order]
    location: Location2D
    routing_heuristic: source_data.RoutingHeuristic = (
        source_data.RoutingHeuristic.random
    )
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    ports: List[port.Queue] = Field(default_factory=list, init=False)

    def to_model(self) -> source_data.OrderSourceData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            source_data.OrderSourceData: An instance of the data object.
        """
        order_source = source_data.OrderSourceData(
            ID=self.ID,
            description="",
            location=self.location,
            order_ids=[order.ID for order in self.orders],
            routing_heuristic=self.routing_heuristic,
        )
        # Store orders for later use in ProductionSystem.to_model()
        self._order_models = [order.to_model() for order in self.orders]
        if not self.ports:
            port_data = [
                prodsys.models.production_system_data.get_default_queue_for_source(order_source)
            ]
            self.ports = [port.Queue(ID=q.ID, capacity=q.capacity, location=q.location, interface_type=q.interface_type) for q in port_data]
        order_source.ports = [q.ID for q in self.ports]
        return order_source
