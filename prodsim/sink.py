from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any, TYPE_CHECKING, Tuple

from pydantic import BaseModel, Field

from . import sim, store
from prodsim.data_structures import sink_data
if TYPE_CHECKING:
    from .factories import material_factory

class Sink(BaseModel):
    env: sim.Environment
    data: sink_data.SinkData
    material_factory: material_factory.MaterialFactory
    # location: List[int]
    # material_type: str
    input_queues: List[store.Queue] = Field(default_factory=list, init=False)

    def add_input_queues(self, input_queues: List[store.Queue]):
        self.input_queues.extend(input_queues)

    def get_location(self) -> Tuple[float, float]:
        return self.data.location
    
# from .factories.material_factory import MaterialFactory
# MaterialFactory.update_forward_refs()
# from .factories import material_factory
# SinkFactory.update_forward_refs()
from .factories import material_factory, queue_factory
# SinkFactory.update_forward_refs()
