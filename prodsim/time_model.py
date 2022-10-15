from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, List, Literal, Optional, Tuple, Union

import numpy as np
from numpy.random import exponential, normal
from pydantic import BaseModel, parse_obj_as, validator

from . import base
from .util import get_class_from_str


def get_constant_list(parameters: List[float], size: int) -> List[float]:
    return [parameters[0]] * size


def get_exponential_list(parameters: List[float], size: int) -> List[float]:
    return list(exponential(parameters[0], size))


def get_normal_list(parameters: List[float], size: int) -> List[float]:
    return list(normal(parameters[0], parameters[1], size))


FUNCTION_DICT: dict = {
    "normal": get_normal_list,
    "constant": get_constant_list,
    "exponential": get_exponential_list,
}


class TimeModel(base.BaseAsset, ABC):
    type: str

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
    type: Literal["FunctionTimeModels"]
    distribution_function: Literal["normal", "exponential", "constant"]
    parameters: List[float]
    batch_size: int
    statistics_buffer: List[float] = []
    distribution_function_object: Callable[[List[float], int], List[float]] = None

    @validator("distribution_function_object", always=True)
    def initialize_distribution_function(cls, v, values):
        return FUNCTION_DICT[values["distribution_function"]]

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
            self.parameters, self.batch_size
        )

    def get_expected_time(
        self,
        origin: Optional[Tuple[float, float]] = None,
        target: Optional[Tuple[float, float]] = None,
    ) -> float:
        return self.parameters[0]


class HistoryTimeModel(TimeModel):
    type: Literal["HistoryTimeModels"]
    history: List[float]

    def get_next_time(
        self,
        origin: Optional[Tuple[float, float]] = None,
        target: Optional[Tuple[float, float]] = None,
    ) -> float:
        return np.random.choice(self.history, 1)[0]

    def get_expected_time(
        self,
        origin: Optional[Tuple[float, float]] = None,
        target: Optional[Tuple[float, float]] = None,
    ) -> float:
        return sum(self.history) / len(self.history)


class ManhattanDistanceTimeModel(TimeModel):
    type: Literal["ManhattanDistanceTimeModel"]
    speed: float
    reaction_time: float

    def get_next_time(
        self,
        origin: Optional[Tuple[float, float]],
        target: Optional[Tuple[float, float]],
    ) -> float:
        x_distance = abs(origin[0] - target[0])
        y_distance = abs(origin[1] - target[1])
        return (x_distance + y_distance) / self.speed + self.reaction_time

    def get_expected_time(
        self,
        origin: Optional[Tuple[float, float]],
        target: Optional[Tuple[float, float]],
    ) -> float:
        return self.get_next_time(origin, target)


class MarkovTimeModel(TimeModel):
    type: Literal["MarkovTimeModel"]

    def get_next_time(self) -> float:
        pass

    def get_expected_time(self, origin, target) -> float:
        pass


CONTEXT = Union[HistoryTimeModel, ManhattanDistanceTimeModel, FunctionTimeModel]


class TimeModelFactory(BaseModel):
    configuration_data: dict
    time_models: Optional[List[TimeModel]] = []

    def create_time_models(self):
        for cls_name, items in self.configuration_data.items():
            # cls = get_class_from_str(cls_name, TIME_MODEL_DICT)
            for values in items.values():
                values.update({"type": cls_name})
                self.add_time_model(values)

    def add_time_model(self, values: dict):
        self.time_models.append(parse_obj_as(CONTEXT, values))

    def get_time_models(self, IDs: List[str]) -> List[TimeModel]:
        return [tm for tm in self.time_models if tm.ID in IDs]

    def get_time_model(self, ID: str) -> TimeModel:
        return [tm for tm in self.time_models if tm.ID == ID].pop()


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
    a = parse_obj_as(CONTEXT, kwargs3)
    print(a)
    print(a.get_expected_time([0, 0], [10, 10]))
    for _ in range(5):
        print(a.get_next_time([0, 0], [10, 10]))
