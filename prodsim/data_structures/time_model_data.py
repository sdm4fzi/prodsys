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


class FunctionTimeModelData(CoreAsset):
    type: Literal[TimeModelEnum.FunctionTimeModel]
    distribution_function: Literal[
        FunctionTimeModelEnum.Constant,
        FunctionTimeModelEnum.Exponential,
        FunctionTimeModelEnum.Normal,
    ]
    parameters: List[float]
    batch_size: int = 100


class ManhattanDistanceTimeModelData(CoreAsset):
    type: Literal[TimeModelEnum.ManhattanDistanceTimeModel]
    speed: float
    reaction_time: float

TIME_MODEL_DATA = Union[
    HistoryTimeModelData, ManhattanDistanceTimeModelData, FunctionTimeModelData
]