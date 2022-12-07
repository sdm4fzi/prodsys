from __future__ import annotations

from typing import List, Literal

from enum import Enum
from .core_asset import CoreAsset
from ..util.statistical_functions import FunctionTimeModelEnum

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
    batch_size: int


class ManhattanDistanceTimeModelData(CoreAsset):
    type: Literal[TimeModelEnum.ManhattanDistanceTimeModel]
    speed: float
    reaction_time: float
