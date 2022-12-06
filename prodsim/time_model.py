from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, List, Literal, Optional, Tuple, Union, Dict

import numpy as np
from numpy.random import exponential, normal
from pydantic import BaseModel, parse_obj_as, validator

from . import base
from . import adapter
from .util import get_class_from_str
from enum import Enum


class TimeModelEnum(str, Enum):
    HistoryTimeModel = "HistoryTimeModel"
    FunctionTimeModel = "FunctionTimeModel"
    ManhattanDistanceTimeModel = "ManhattanDistanceTimeModel"


class FunctionTimeModelEnum(str, Enum):
    Constant = "constant"
    Exponential = "exponential"
    Normal = "normal"


class HistoryTimeModelData(base.BaseAsset):
    type: Literal[TimeModelEnum.HistoryTimeModel]
    history: List[float]


class FunctionTimeModelData(base.BaseAsset):
    type: Literal[TimeModelEnum.FunctionTimeModel]
    distribution_function: Literal[
        FunctionTimeModelEnum.Constant,
        FunctionTimeModelEnum.Exponential,
        FunctionTimeModelEnum.Normal,
    ]
    parameters: List[float]
    batch_size: int


class ManhattanDistanceTimeModelData(base.BaseAsset):
    type: Literal[TimeModelEnum.ManhattanDistanceTimeModel]
    speed: float
    reaction_time: float


def get_constant_list(parameters: List[float], size: int) -> List[float]:
    return [parameters[0]] * size


def get_exponential_list(parameters: List[float], size: int) -> List[float]:
    return list(exponential(parameters[0], size))


def get_normal_list(parameters: List[float], size: int) -> List[float]:
    return list(normal(parameters[0], parameters[1], size))


FUNCTION_DICT: Dict[str, Callable[[List[float], int], List[float]]] = {
    FunctionTimeModelEnum.Normal: get_normal_list,
    FunctionTimeModelEnum.Constant: get_constant_list,
    FunctionTimeModelEnum.Exponential: get_exponential_list,
}


class TimeModel(ABC, BaseModel):
    @abstractmethod
    def get_next_time(
        self,
        origin: Optional[Tuple[float, float]],
        target: Optional[Tuple[float, float]],
    ) -> float:
        pass

    @abstractmethod
    def get_expected_time(
        self,
        origin: Optional[Tuple[float, float]],
        target: Optional[Tuple[float, float]],
    ) -> float:
        pass


class FunctionTimeModel(TimeModel):
    time_model_data: FunctionTimeModelData
    statistics_buffer: List[float] = []
    distribution_function_object: Callable[
        [List[float], int], List[float]
    ] = get_constant_list

    @validator("distribution_function_object", always=True)
    def initialize_distribution_function(cls, v, values):
        return FUNCTION_DICT[values["time_model_data"].distribution_function]

    def get_next_time(
        self,
        origin: Optional[Tuple[float, float]] = None,
        target: Optional[Tuple[float, float]] = None,
    ) -> float:
        try:
            value = self.statistics_buffer.pop()
            if value < 0:
                return 0.1
            return value
        except IndexError:
            self._fill_buffer()
            return self.get_next_time()

    def _fill_buffer(self):
        self.statistics_buffer = self.distribution_function_object(
            self.time_model_data.parameters, self.time_model_data.batch_size
        )

    def get_expected_time(
        self,
        origin: Optional[Tuple[float, float]] = None,
        target: Optional[Tuple[float, float]] = None,
    ) -> float:
        return self.time_model_data.parameters[0]


class HistoryTimeModel(TimeModel):
    time_model_data: HistoryTimeModelData

    def get_next_time(
        self,
        origin: Optional[Tuple[float, float]] = None,
        target: Optional[Tuple[float, float]] = None,
    ) -> float:
        return np.random.choice(self.time_model_data.history, 1)[0]

    def get_expected_time(
        self,
        origin: Optional[Tuple[float, float]] = None,
        target: Optional[Tuple[float, float]] = None,
    ) -> float:
        return sum(self.time_model_data.history) / len(self.time_model_data.history)


class ManhattanDistanceTimeModel(TimeModel):
    time_model_data: ManhattanDistanceTimeModelData

    def get_next_time(
        self,
        origin: Tuple[float, float],
        target: Tuple[float, float],
    ) -> float:
        x_distance = abs(origin[0] - target[0])
        y_distance = abs(origin[1] - target[1])
        return (
            x_distance + y_distance
        ) / self.time_model_data.speed + self.time_model_data.reaction_time

    def get_expected_time(
        self,
        origin: Tuple[float, float],
        target: Tuple[float, float],
    ) -> float:
        return self.get_next_time(origin, target)


class MarkovTimeModel(TimeModel):
    # TODO: Add time model based on Markov chains

    def get_next_time(self) -> float:
        return 0.0

    def get_expected_time(self, origin, target) -> float:
        return 0.0


TIME_MODEL_DATA = Union[
    HistoryTimeModelData, ManhattanDistanceTimeModelData, FunctionTimeModelData
]
TIME_MODEL = Union[HistoryTimeModel, ManhattanDistanceTimeModel, FunctionTimeModel]


class TimeModelFactory(BaseModel):
    time_model_data: List[TIME_MODEL_DATA] = []
    time_models: List[TIME_MODEL] = []

    def create_time_model_from_configuration_data(self, configuration_data: dict):
        for cls_name, items in configuration_data.items():
            # cls = get_class_from_str(cls_name, TIME_MODEL_DICT)
            for values in items.values():
                values.update({"type": cls_name})
                self.add_time_model(values)

    def create_time_model_from_adapter(self, adapter: adapter.Adapter):
        for time_model_data in adapter.time_model_data:
            self.time_models.append(
                parse_obj_as(TIME_MODEL, {"time_model_data": time_model_data})
            )

    def create_time_models_from_objects(self, time_model_data: List[TIME_MODEL_DATA]):
        for values in time_model_data:
            self.time_model_data.append(values)

    def add_time_model(self, values: dict):
        self.time_model_data.append(parse_obj_as(TIME_MODEL_DATA, values))
        self.time_models.append(
            parse_obj_as(TIME_MODEL, {"time_model_data": self.time_model_data[-1]})
        )

    def get_time_models(self, IDs: List[str]) -> List[TimeModel]:
        return [tm for tm in self.time_models if tm.time_model_data.ID in IDs]

    def get_time_model(self, ID: str) -> TimeModel:
        return [tm for tm in self.time_models if tm.time_model_data.ID == ID].pop()


if __name__ == "__main__":
    kwargs = {
        "ID": "F",
        "description": "FTMO",
        "type": "FunctionTimeModels",
        "distribution_function": "normal",
        "parameters": [1.3, 2.0],
        "batch_size": 100,
    }
    kwargs2 = {
        "ID": "H",
        "description": "HTMO",
        "type": "HistoryTimeModels",
        "history": [1.3, 2.0],
    }
    kwargs3 = {
        "ID": "MDT",
        "description": "MDTMO",
        "type": "ManhattanDistanceTimeModel",
        "speed": 12,
        "reaction_time": 1.1,
    }
    # a = FunctionTimeModel(**kwargs)
