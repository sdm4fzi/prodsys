"""
The `time_model` module contains classes to specify time models in the simulation for the arrival
of products, performance of processes and transports and the duration of states.

The following time models are possible:
- `SequentialTimeModelData`: A time model that is based on a sequence of values.
- `FunctionTimeModelData`: A time model that is based on a distribution function which gets sampled.
- `ManhattanDistanceTimeModelData`: A time model that is based on the manhattan distance between two nodes and a constant velocity.
"""

from __future__ import annotations

from typing import List, Literal, Union
from pydantic import Field

from enum import Enum
from prodsys.models.core_asset import CoreAsset
from prodsys.util.statistical_functions import FunctionTimeModelEnum


class TimeModelEnum(str, Enum):
    """
    Enum that represents the different kind time models.

    - HistoryTimeModel: A time model that is based on a sequence of values.
    - FunctionTimeModel: A time model that is based on a distribution function which gets sampled.
    - ManhattanDistanceTimeModel: A time model that is based on the manhattan distance between two nodes and a constant velocity.
    """

    HistoryTimeModel = "HistoryTimeModel"
    FunctionTimeModel = "FunctionTimeModel"
    ManhattanDistanceTimeModel = "ManhattanDistanceTimeModel"


class SequentialTimeModelData(CoreAsset):
    """
    Class that represents a time model that is based on a sequence of values.

    Args:
        ID (str): ID of the time model.
        description (str): Description of the time model.
        sequence (List[float]): Sequence of time values.

    Examples:
        Sequential time model with 7 time values:
        ```	py
        import prodsys
        prodsys.time_model_data.SequentialTimeModelData(
            ID="sequence_time_model_1",
            description="Examplary sequence time model",
            sequence=[25.0, 13.0, 15.0, 16.0, 17.0, 20.0, 21.0],
        )
        ```
    """

    sequence: List[float]

    class Config:
        schema_extra = {
            "example": {
                "summary": "Sequential time model",
                "value": {
                    "ID": "sequence_time_model_1",
                    "description": "Examplary sequence time model",
                    "sequence": [25.0, 13.0, 15.0, 16.0, 17.0, 20.0, 21.0],
                },
            }
        }


class FunctionTimeModelData(CoreAsset):
    """
    Class that represents a time model that is based on a function and represents the timely values by their distribution function.

    Args:
        ID (str): ID of the time model.
        description (str): Description of the time model.
        distribution_function (FunctionTimeModelEnum): Zype of the distribution function of the time model.
        location (float): Location parameter of the distribution function.
        scale (float): Scale parameter of the distribution function.

    Examples:
        Normal distribution time model with 20 minutes:
        ``` py
        import prodsys
        prodsys.time_model_data.FunctionTimeModelData(
            ID="function_time_model_1",
            description="normal distribution time model with 20 minutes",
            distribution_function=prodsys.FunctionTimeModelEnum.normal,
            location=20.0,
            scale=5.0,
        )
        ```
    """

    distribution_function: FunctionTimeModelEnum
    location: float
    scale: float
    batch_size: int = Field(default=100, init=False)

    class Config:
        schema_extra = {
            "example": {
                "summary": "Function time model",
                "value": {
                    "ID": "function_time_model_1",
                    "description": "normal distribution time model with 20 minutes",
                    "distribution_function": "normal",
                    "location": 20.0,
                    "scale": 5.0,
                },
            }
        }


class ManhattanDistanceTimeModelData(CoreAsset):
    """
    Class that represents a time model that is based on the manhattan distance between two nodes and a constant velocity.

    Args:
        ID (str): ID of the time model.
        description (str): Description of the time model.
        speed (float): Speed of the transport.
        reaction_time (float): Reaction time of the transport.

    Examples:
        Manhattan time model with speed 180 m/min = 3 m/s and reaction time 0.15 minutes:
        ``` py
        import prodsys
        time_model_data.ManhattanDistanceTimeModelData(
            ID="manhattan_time_model_1",
            description="manhattan time model with speed 180 m/min = 3 m/s",
            speed=180.0,
            reaction_time=0.15,
        )
    """

    speed: float
    reaction_time: float

    class Config:
        schema_extra = {
            "example": {
                "summary": "Manhattan time model",
                "value": {
                    "ID": "manhattan_time_model_1",
                    "description": "manhattan time model with speed 180 m/min = 3 m/s",
                    "speed": 30.0,
                    "reaction_time": 0.15,
                },
            }
        }


TIME_MODEL_DATA = Union[
    SequentialTimeModelData, ManhattanDistanceTimeModelData, FunctionTimeModelData
]
