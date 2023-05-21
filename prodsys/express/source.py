from typing import List, Optional, Union
from uuid import uuid1

from abc import ABC

from pydantic import Field, conlist
from pydantic.dataclasses import dataclass

from prodsys.data_structures import core_asset, source_data, queue_data
import prodsys

from prodsys.express import process, state, core, material, time_model

@dataclass
class Source(core.ExpressObject):
    """
    Class that represents a source.

    Args:
        material (material.Material): Material of the source.
        time_model (time_model.TIME_MODEL_UNION): Time model of the source that determines the inter-arrival time of materials.
        location (conlist(float, min_items=2, max_items=2)): Location of the source.
        router (source_data.RouterType, optional): Router of the source. Defaults to source_data.RouterType.SimpleRouter.
        routing_heuristic (source_data.RoutingHeuristic, optional): Routing heuristic of the source. Defaults to source_data.RoutingHeuristic.shortest_queue.
        ID (str): ID of the source.
    
    Attributes:
        _output_queues (List[queue_data.QueueData]): Output queues of the source.

    Examples:
        Creation of a source with a material, a time model and a location:
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
        >>> arrival_time_model = psx.time_model_data.FunctionTimeModel(
        ...     distribution_function="exponential",
        ...     scale=10.0,
        ... )
        >>> psx.Source(
        ...     material=material,
        ...     time_model=arrival_time_model,
        ...     location=[0.0, 0.0],
        ... )
    """
    material: material.Material
    time_model: time_model.TIME_MODEL_UNION
    location: conlist(float, min_items=2, max_items=2)
    router: source_data.RouterType = source_data.RouterType.SimpleRouter
    routing_heuristic: source_data.RoutingHeuristic = source_data.RoutingHeuristic.shortest_queue
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    _output_queues: List[queue_data.QueueData] = Field(default_factory=list, init=False)


    def __post_init_post_parse__(self):
        pass

    def to_data_object(self) -> source_data.SourceData:
        source = source_data.SourceData(
            ID=self.ID,
            description="",
            location=self.location,
            material_type=self.material.ID,
            time_model_id=self.time_model.ID,
            router=self.router,
            routing_heuristic=self.routing_heuristic,
        )
        self._output_queues = [prodsys.adapters.get_default_queue_for_source(source)]
        source.output_queues = [q.ID for q in self._output_queues]
        return source
