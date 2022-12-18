from __future__ import annotations

from typing import List, TYPE_CHECKING, Tuple

from pydantic import BaseModel, Field
from simpy import events

from prodsim.simulation import router, sim, store, time_model
from prodsim.data_structures import source_data, material_data

if TYPE_CHECKING:
    from prodsim.factories import material_factory


class Source(BaseModel):
    env: sim.Environment
    data: source_data.SourceData
    material_data: material_data.MaterialData
    material_factory: material_factory.MaterialFactory
    time_model: time_model.TimeModel
    router: router.Router
    output_queues: List[store.Queue] = Field(default_factory=list, init=False)

    class Config:
        arbitrary_types_allowed = True

    def add_output_queues(self, output_queues: List[store.Queue]):
        self.output_queues.extend(output_queues)

    def start_source(self):
        self.env.process(self.create_material_loop())

    def create_material_loop(self):
        while True:
            yield self.env.timeout(self.time_model.get_next_time())
            material = self.material_factory.create_material(
                self.material_data, self.router
            )
            available_events_events = []
            for queue in self.output_queues:
                available_events_events.append(queue.put(material.material_data))
            yield events.AllOf(self.env, available_events_events)

            material.process = self.env.process(material.process_material())
            material.next_resource = self

    def get_location(self) -> Tuple[float, float]:
        return self.data.location
    
from prodsim.factories import material_factory
Source.update_forward_refs()