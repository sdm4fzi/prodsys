from __future__ import annotations

from typing import List, Dict
from dataclasses import dataclass, field

import base
import env
import material
import store

@dataclass
class Sink(base.IDEntity):
    env: env.Environment
    material_factory: material.MaterialFactory
    location: List[int]
    material_type: str
    input_queues: List[store.Queue] = field(default_factory=list, init=False)

    def add_input_queues(self, input_queues: List[store.Queue]):
        self.input_queues.extend(input_queues)

    def get_location(self) -> List[int]:
        return self.location


@dataclass
class SinkFactory:
    data: dict
    env: env.Environment
    material_factory: material.MaterialFactory
    queue_factory: store.QueueFactory

    sinks: List[Sink] = field(default_factory=list, init=False)

    def create_sinks(self):
        sources = self.data['sinks']
        for values in sources.values():
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