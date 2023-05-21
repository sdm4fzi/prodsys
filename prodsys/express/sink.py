from typing import List, Optional
from uuid import uuid1


from pydantic import Field, conlist
from pydantic.dataclasses import dataclass

from prodsys.data_structures import sink_data, queue_data
import prodsys

from prodsys.express import core, material

@dataclass
class Sink(core.ExpressObject):
    """
    Class that represents a sink.

    Args:
        material (material.Material): Material of the sink.
        location (conlist(float, min_items=2, max_items=2)): Location of the sink.
        ID (str): ID of the sink.
    
    Attributes:
        _input_queues (List[queue_data.QueueData]): Input queues of the sink.
    
    Examples:
        Creation of a sink with a material and a location:
        >>> import prodsys.express as psx
        >>> welding_time_model = psx.time_model_data.FunctionTimeModel(
        ...     distribution_function="normal",
        ...     location=20.0,
        ...     scale=5.0,
        ... )
        >>> welding_process_1 = psx.process.ProductionProcess(
        ...     time_model=welding_time_model,
        ... )
        >>> welding_process_2 = psx.process.ProductionProcess(
        ...     time_model=welding_time_model,
        ... )
        >>> transport_time_model = psx.time_model_data.ManhattenDistanceTimeModel(
        ...     speed=10,
        ...     reaction_time= 0.3
        ... )
        >>> transport_process = psx.process.TransportProcess(
        ...     time_model=transport_time_model,
        ... )
        >>> psx.Material(
        ...     processes=[welding_process_1, welding_process_2],
        ...     transport_process=transport_process
        ... )
        >>> psx.Sink(
        ...     material=material,
        ...     location=[0.0, 0.0],
        ... )
    """
    material: material.Material
    location: conlist(float, min_items=2, max_items=2)
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    _input_queues: List[queue_data.QueueData] = Field(default_factory=list, init=False)

    def to_data_object(self) -> sink_data.SinkData:
        """
        Converts the express object to a data object.

        Returns:
            sink_data.SinkData: Data object of the express object.
        """
        sink = sink_data.SinkData(
            ID=self.ID,
            description="",
            location=self.location,
            material_type=self.material.ID,
        )
        self._input_queues = [prodsys.adapters.get_default_queue_for_sink(sink)]
        sink.input_queues = [q.ID for q in self._input_queues]
        return sink
