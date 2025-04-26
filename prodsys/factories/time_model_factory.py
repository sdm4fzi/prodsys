from __future__ import annotations

from typing import Dict, List, TYPE_CHECKING

from prodsys.models.time_model_data import TIME_MODEL_DATA, TimeModelEnum
from prodsys.simulation.time_model import FunctionTimeModel, SampleTimeModel, ScheduledTimeModel, DistanceTimeModel, TIME_MODEL, TimeModel

if TYPE_CHECKING:
    from prodsys.adapters import adapter

TIME_MODEL_MAP = {
    "FunctionTimeModelData": FunctionTimeModel,
    "SampleTimeModelData": SampleTimeModel,
    "ScheduledTimeModelData": ScheduledTimeModel,
    "DistanceTimeModelData": DistanceTimeModel,
}

class TimeModelFactory:
    """
    Factory class that creates and stores `prodsys.simulation` time model objects based on the given time model data according to `prodsys.models.time_model_data.TIME_MODEL_DATA`.

    Returns:
        _type_: _description_
    """
    def __init__(self):
        """
        Initializes the TimeModelFactory with the given adapter.

        Args:
            adapter (adapter.ProductionSystemAdapter): Adapter that contains the time model data.
        """
        self.time_model_data: List[TIME_MODEL_DATA] = []
        self.time_models: Dict[str, TIME_MODEL] = {}

    def get_class(self, time_model_data: TIME_MODEL_DATA) -> TIME_MODEL:
        """
        Returns the class of the time model based on the given time model data.

        Args:
            time_model_data (TIME_MODEL_DATA): Time model data that is used to determine the class.

        Returns:
            TIME_MODEL: Class of the time model.
        """
        class_name = time_model_data.__class__.__name__
        if class_name in TIME_MODEL_MAP:
            return TIME_MODEL_MAP[class_name]
        else:
            raise ValueError(f"Unknown time model data class: {class_name}")

    def create_time_models(self, adapter: adapter.ProductionSystemAdapter):
        """
        Creates time model objects based on the given adapter.

        Args:
            adapter (adapter.ProductionSystemAdapter): Adapter that contains the time model data.
        """
        for time_model_data in adapter.time_model_data:
            time_model_class = self.get_class(time_model_data)
            
            time_model = time_model_class(time_model_data)
            self.time_models[time_model_data.ID] = time_model

    def get_time_models(self, IDs: List[str]) -> List[TimeModel]:
        """
        Returns a list of time model objects with the given IDs.

        Args:
            IDs (List[str]): List of IDs that is used to filter the time model objects.

        Returns:
            List[time_model.TimeModel]: List of time model objects with the given IDs.
        """
        return [self.time_models[ID] for ID in IDs if ID in self.time_models]

    def get_time_model(self, ID: str) -> TimeModel:
        """
        Returns a time model object with the given ID.

        Args:
            ID (str): ID that is used to filter the time model objects.

        Returns:
            time_model.TimeModel: Time model object with the given ID.
        """
        if ID in self.time_models:
            return self.time_models[ID]
        else:
            raise ValueError(f"Time model with ID {ID} not found.")