from __future__ import annotations

from typing import List, Tuple

from pydantic import BaseModel, Field

from prodsim.simulation import sim, store
from prodsim.data_structures import sink_data


class Sink(BaseModel):
    env: sim.Environment
    data: sink_data.SinkData
    material_factory: material_factory.MaterialFactory
    input_queues: List[store.Queue] = Field(default_factory=list, init=False)

    class Config:
        arbitrary_types_allowed = True

    def add_input_queues(self, input_queues: List[store.Queue]):
        self.input_queues.extend(input_queues)

    def get_location(self) -> Tuple[float, float]:
        return self.data.location
    
from prodsim.factories import material_factory
Sink.update_forward_refs()
    

