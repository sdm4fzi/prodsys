from __future__ import annotations

from typing import List, TYPE_CHECKING

from pydantic import BaseModel, parse_obj_as

from prodsys.data_structures import time_model_data
from prodsys.simulation import time_model

if TYPE_CHECKING:
    from prodsys.adapters import adapter

class TimeModelFactory(BaseModel):
    time_model_data: List[time_model_data.TIME_MODEL_DATA] = []
    time_models: List[time_model.TIME_MODEL] = []

    def create_time_models(self, adapter: adapter.ProductionSystemAdapter):
        for time_model_data in adapter.time_model_data:
            self.time_models.append(
                parse_obj_as(time_model.TIME_MODEL, {"time_model_data": time_model_data})
            )

    def add_time_model(self, values: dict):
        self.time_model_data.append(parse_obj_as(time_model_data.TIME_MODEL_DATA, values))
        self.time_models.append(
            parse_obj_as(time_model.TIME_MODEL, {"time_model_data": self.time_model_data[-1]})
        )

    def get_time_models(self, IDs: List[str]) -> List[time_model.TimeModel]:
        return [tm for tm in self.time_models if tm.time_model_data.ID in IDs]

    def get_time_model(self, ID: str) -> time_model.TimeModel:
        return [tm for tm in self.time_models if tm.time_model_data.ID == ID].pop()
