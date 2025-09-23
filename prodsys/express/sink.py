from __future__ import annotations

from typing import List, Optional
from uuid import uuid1


from pydantic import Field, conlist
from pydantic.dataclasses import dataclass

from prodsys.express import core, port

from prodsys.models import port_data, sink_data
import prodsys
import prodsys.models
from prodsys.models.core_asset import Location2D
import prodsys.models.production_system_data


@dataclass
class Sink(core.ExpressObject):
    """
    Class that represents a sink.

    Args:
        product (product.Product): Product of the sink.
        location (conlist(float, min_length=2, max_length=2)): Location of the sink.
        ID (str): ID of the sink.

    Attributes:
        _input_queues (List[queue_data.QueueData]): Input queues of the sink.

    Examples:
        Creation of a sink with a product and a location:
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
        psx.Sink(
            product=product,
            location=[0.0, 0.0],
        )
        ```
    """

    product: product.Product
    location: Location2D
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    ports: List[port.Queue] = Field(default_factory=list, init=False)

    def to_model(self) -> sink_data.SinkData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            sink_data.SinkData: Data object of the express object.
        """
        sink = sink_data.SinkData(
            ID=self.ID,
            description="",
            location=self.location,
            product_type=self.product.ID,
        )
        if not self.ports:
            port_data = [
                prodsys.models.production_system_data.get_default_queue_for_sink(sink)
            ]
            self.ports = [port.Queue(ID=q.ID, capacity=q.capacity, location=q.location, interface_type=q.interface_type) for q in port_data]
        sink.ports = [q.ID for q in self.ports]
        return sink


from prodsys.express import product
