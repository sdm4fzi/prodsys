from __future__ import annotations

from typing import List, Literal, Union

from enum import Enum
from prodsim.data_structures.core_asset import CoreAsset
from prodsim.util.statistical_functions import FunctionTimeModelEnum


class TimeModelEnum(str, Enum):
    HistoryTimeModel = "HistoryTimeModel"
    FunctionTimeModel = "FunctionTimeModel"
    ManhattanDistanceTimeModel = "ManhattanDistanceTimeModel"


class HistoryTimeModelData(CoreAsset):
    type: Literal[TimeModelEnum.HistoryTimeModel]
    history: List[float]

    class Config:
        schema_extra = {
            "example": {
                "ID": "history_time_model_1",
                "description": "history time model",
                "type": "HistoryTimeModel",
                "history": [25.0, 13.0, 15.0, 16.0, 17.0, 20.0, 21.0],
            }
        }


class FunctionTimeModelData(CoreAsset):
    type: Literal[TimeModelEnum.FunctionTimeModel]
    distribution_function: Literal[
        FunctionTimeModelEnum.Constant,
        FunctionTimeModelEnum.Exponential,
        FunctionTimeModelEnum.Normal,
    ]
    parameters: List[float]
    batch_size: int = 100

    class Config:
        schema_extra = {
            "example": {
                "ID": "function_time_model_1",
                "description": "normal distribution time model with 20 minutes",
                "type": "FunctionTimeModel",
                "distribution_function": "normal",
                "parameters": [14.3, 5.0],
                "batch_size": 100,
            }
        }


class ManhattanDistanceTimeModelData(CoreAsset):
    type: Literal[TimeModelEnum.ManhattanDistanceTimeModel]
    speed: float
    reaction_time: float

    class Config:
        schema_extra = {
            "example": {
                "ID": "manhattan_time_model_1",
                "description": "manhattan time model with speed 180 m/min = 3 m/s",
                "type": "ManhattanDistanceTimeModel",
                "speed": 30.0,
                "reaction_time": 0.15,
            }
        }


TIME_MODEL_DATA = Union[
    HistoryTimeModelData, ManhattanDistanceTimeModelData, FunctionTimeModelData
]
