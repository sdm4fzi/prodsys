from __future__ import annotations

from typing import List, Optional
from uuid import uuid1


from pydantic import Field, conlist
from pydantic.dataclasses import dataclass

from prodsys.express import core, time_model

from prodsys.models import port_data, source_data
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

    product: product.Product
    time_model: time_model.TIME_MODEL_UNION
    location: Location2D
    routing_heuristic: source_data.RoutingHeuristic = (
        source_data.RoutingHeuristic.random
    )
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    ports: List[port_data.QueueData] = Field(default_factory=list, init=False)

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
        self.ports = [
            prodsys.models.production_system_data.get_default_queue_for_source(source)
        ]
        source.ports = [q.ID for q in self.ports]
        return source


from prodsys.express import product
