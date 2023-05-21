from __future__ import annotations

from typing import List, TYPE_CHECKING

from pydantic import BaseModel, parse_obj_as

from prodsys.data_structures import time_model_data
from prodsys.simulation import time_model

if TYPE_CHECKING:
    from prodsys.adapters import adapter

class TimeModelFactory(BaseModel):
    """
    Factory class that creates and stores `prodsys.simulation` time model objects based on the given time model data according to `prodsys.data_structures.time_model_data.TIME_MODEL_DATA`.

    Args:

    Returns:
        _type_: _description_
    """
    time_model_data: List[time_model_data.TIME_MODEL_DATA] = []
    time_models: List[time_model.TIME_MODEL] = []

    def create_time_models(self, adapter: adapter.ProductionSystemAdapter):
        """
        Creates time model objects based on the given adapter.

        Args:
            adapter (adapter.ProductionSystemAdapter): Adapter that contains the time model data.
        """
        for time_model_data in adapter.time_model_data:
            self.time_models.append(
                parse_obj_as(time_model.TIME_MODEL, {"time_model_data": time_model_data})
            )

    def get_time_models(self, IDs: List[str]) -> List[time_model.TimeModel]:
        """
        Returns a list of time model objects with the given IDs.

        Args:
            IDs (List[str]): List of IDs that is used to filter the time model objects.

        Returns:
            List[time_model.TimeModel]: List of time model objects with the given IDs.
        """
        return [tm for tm in self.time_models if tm.time_model_data.ID in IDs]

    def get_time_model(self, ID: str) -> time_model.TimeModel:
        """
        Returns a time model object with the given ID.

        Args:
            ID (str): ID that is used to filter the time model objects.

        Returns:
            time_model.TimeModel: Time model object with the given ID.
        """
        return [tm for tm in self.time_models if tm.time_model_data.ID == ID].pop()
