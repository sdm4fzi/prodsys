from __future__ import annotations

from typing import List, Literal, Union

from enum import Enum
from prodsim.data_structures.core_asset import CoreAsset
from prodsim.util.statistical_functions import FunctionTimeModelEnum


class TimeModelEnum(str, Enum):
    HistoryTimeModel = "HistoryTimeModel"
    FunctionTimeModel = "FunctionTimeModel"
    ManhattanDistanceTimeModel = "ManhattanDistanceTimeModel"


class SequentialTimeModelData(CoreAsset):
    sequence: List[float]

    class Config:
        schema_extra = {
            "example": {
                "ID": "history_time_model_1",
                "description": "history time model",
                "sequence": [25.0, 13.0, 15.0, 16.0, 17.0, 20.0, 21.0],
            }
        }


class FunctionTimeModelData(CoreAsset):
    distribution_function: FunctionTimeModelEnum
    location: float
    scale: float
    batch_size: int = 100

    class Config:
        schema_extra = {
            "example": {
                "ID": "function_time_model_1",
                "description": "normal distribution time model with 20 minutes",
                "distribution_function": "normal",
                "location": 20.0,
                "scale": 5.0,
                "batch_size": 100,
            }
        }


class ManhattanDistanceTimeModelData(CoreAsset):
    speed: float
    reaction_time: float

    class Config:
        schema_extra = {
            "example": {
                "ID": "manhattan_time_model_1",
                "description": "manhattan time model with speed 180 m/min = 3 m/s",
                "speed": 30.0,
                "reaction_time": 0.15,
            }
        }


TIME_MODEL_DATA = Union[
    SequentialTimeModelData, ManhattanDistanceTimeModelData, FunctionTimeModelData
]
