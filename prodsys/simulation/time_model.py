from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, List, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, validator

from prodsys.data_structures.time_model_data import (
    FunctionTimeModelData,
    SequentialTimeModelData,
    ManhattanDistanceTimeModelData,
)
from prodsys.util.statistical_functions import FUNCTION_DICT, FunctionTimeModelEnum


class TimeModel(ABC, BaseModel):
    @abstractmethod
    def get_next_time(
        self,
        origin: Optional[List[float]] = None, # TOOO: rework this with kwargs
        target: Optional[List[float]] = None,
    ) -> float:
        pass

    @abstractmethod
    def get_expected_time(
        self,
        origin: Optional[List[float]] = None,
        target: Optional[List[float]] = None,
    ) -> float:
        pass


class FunctionTimeModel(TimeModel):
    time_model_data: FunctionTimeModelData
    statistics_buffer: List[float] = []
    distribution_function_object: Callable[
        [FunctionTimeModelData], List[float]
    ] = FUNCTION_DICT[FunctionTimeModelEnum.Constant]

    @validator("distribution_function_object", always=True)
    def initialize_distribution_function(cls, v, values):
        return FUNCTION_DICT[values["time_model_data"].distribution_function]

    def get_next_time(
        self,
        origin: Optional[List[float]] = None,
        target: Optional[List[float]] = None,
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
            self.time_model_data
        )

    def get_expected_time(
        self,
        origin: Optional[List[float]] = None,
        target: Optional[List[float]] = None,
    ) -> float:
        return self.time_model_data.location


class SequentialTimeModel(TimeModel):
    time_model_data: SequentialTimeModelData

    def get_next_time(
        self,
        origin: Optional[List[float]] = None,
        target: Optional[List[float]] = None,
    ) -> float:
        return np.random.choice(self.time_model_data.sequence, 1)[0]

    def get_expected_time(
        self,
        origin: Optional[List[float]] = None,
        target: Optional[List[float]] = None,
    ) -> float:
        return sum(self.time_model_data.sequence) / len(self.time_model_data.sequence)


class ManhattanDistanceTimeModel(TimeModel):
    time_model_data: ManhattanDistanceTimeModelData

    def get_next_time(
        self,
        origin: Optional[List[float]] = None,
        target: Optional[List[float]] = None,
    ) -> float:
        if origin is None or target is None:
            raise ("Origin and target must be defined for ManhattanDistanceTimeModel")  # type: ignore
        x_distance = abs(origin[0] - target[0])
        y_distance = abs(origin[1] - target[1])
        return (
            x_distance + y_distance
        ) / self.time_model_data.speed + self.time_model_data.reaction_time

    def get_expected_time(
        self,
        origin: Optional[List[float]] = None,
        target: Optional[List[float]] = None,
    ) -> float:
        if origin is None or target is None:
            raise ("Origin and target must be defined for ManhattanDistanceTimeModel")  # type: ignore
        return self.get_next_time(origin, target)


TIME_MODEL = Union[SequentialTimeModel, ManhattanDistanceTimeModel, FunctionTimeModel]
