from typing import List, Optional
from uuid import uuid1


from pydantic import Field, conlist
from pydantic.dataclasses import dataclass

from prodsys.models import sink_data, queue_data
import prodsys

from prodsys.express import core, product

@dataclass
class Sink(core.ExpressObject):
    """
    Class that represents a sink.

    Args:
        product (product.Product): Product of the sink.
        location (conlist(float, min_items=2, max_items=2)): Location of the sink.
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
    location: conlist(float, min_items=2, max_items=2)
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    _input_queues: List[queue_data.QueueData] = Field(default_factory=list, init=False)

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
        self._input_queues = [prodsys.adapters.get_default_queue_for_sink(sink)]
        sink.input_queues = [q.ID for q in self._input_queues]
        return sink
