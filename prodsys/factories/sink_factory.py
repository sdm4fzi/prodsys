from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any, TYPE_CHECKING

from pydantic import BaseModel, Field, parse_obj_as

from prodsys.simulation import sim, sink
from prodsys.data_structures import sink_data
if TYPE_CHECKING:
    from prodsys.factories import material_factory, queue_factory
    from prodsys.adapters import adapter


class SinkFactory(BaseModel):
    env: sim.Environment
    material_factory: material_factory.MaterialFactory
    queue_factory: queue_factory.QueueFactory

    sinks: List[sink.Sink] = Field(default_factory=list, init=False)

    class Config:
        arbitrary_types_allowed = True

    def create_sinks(self, adapter: adapter.ProductionSystemAdapter):
        for data in adapter.sink_data:
            self.add_sink(data)

    def add_sink(self, sink_data: sink_data.SinkData):
        values = {
            "env": self.env,
            "data": sink_data,
            "material_factory": self.material_factory,
        }
        sink_object = parse_obj_as(sink.Sink, values)
        self.add_queues_to_sink(sink_object)
        self.sinks.append(sink_object)

    def add_queues_to_sink(self, _sink: sink.Sink):
        input_queues = self.queue_factory.get_queues(_sink.data.input_queues)
        _sink.add_input_queues(input_queues)

    def get_sink(self, ID) -> sink.Sink:
        return [s for s in self.sinks if s.data.ID == ID].pop()

    def get_sinks(self, IDs: List[str]) -> List[sink.Sink]:
        return [s for s in self.sinks if s.data.ID in IDs]

    def get_sinks_with_material_type(self, __material_type: str):
        return [s for s in self.sinks if __material_type == s.data.material_type]

from prodsys.factories import material_factory, queue_factory   
SinkFactory.update_forward_refs()