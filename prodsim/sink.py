from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any, TYPE_CHECKING

from pydantic import BaseModel, Field

from . import base, sim, store
if TYPE_CHECKING:
    from .factories import material_factory, queue_factory


@dataclass
class Sink(base.IDEntity):
    env: sim.Environment
    data: Any
    material_factory: material_factory.MaterialFactory
    location: List[int]
    material_type: str
    input_queues: List[store.Queue] = field(default_factory=list, init=False)

    def add_input_queues(self, input_queues: List[store.Queue]):
        self.input_queues.extend(input_queues)

    def get_location(self) -> List[int]:
        return self.location


class SinkFactory(BaseModel):
    data: dict
    env: sim.Environment
    material_factory: material_factory.MaterialFactory
    queue_factory: queue_factory.QueueFactory

    sinks: List[Sink] = Field(default_factory=list, init=False)

    def create_sinks(self):
        for values in self.data.values():
            self.add_sink(values)

    def add_sink(self, values: dict):
        sink = Sink(ID=values['ID'], description=values['description'], location=values["location"],
                        env=self.env, material_factory=self.material_factory,
                        material_type=values['material_type']
                        )
        self.add_queues_to_sink(sink, values)
        self.sinks.append(sink)

    def add_queues_to_sink(self, _sink: Sink, values: Dict):
        if 'input_queues' in values.keys():
            input_queues = self.queue_factory.get_queues(values['input_queues'])
            _sink.add_input_queues(input_queues)

    def get_sink(self, ID) -> Sink:
        return [s for s in self.sinks if s.ID == ID].pop()

    def get_sinks(self, IDs: List[str]) -> List[Sink]:
        return [s for s in self.sinks if s.ID in IDs]

    def get_sinks_with_material_type(self, __material_type: str):
        return [s for s in self.sinks if __material_type == s.material_type]
    
from . factories import material_factory
