from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, List, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, validator

from prodsys.models.time_model_data import (
    FunctionTimeModelData,
    SequentialTimeModelData,
    ManhattanDistanceTimeModelData,
)
from prodsys.util.statistical_functions import FUNCTION_DICT, FunctionTimeModelEnum


class TimeModel(ABC, BaseModel):
    """
    Abstract base class for time models.
    """
    @abstractmethod
    def get_next_time(
        self,
        origin: Optional[List[float]] = None, # TOOO: rework this with kwargs
        target: Optional[List[float]] = None,
    ) -> float:
        """
        Returns the next time of the time model.

        Args:
            origin (Optional[List[float]], optional): The origin of the product for a transport. Defaults to None.
            target (Optional[List[float]], optional): The target of the product for a transport. Defaults to None.

        Returns:
            float: The next time of the time model.
        """
        pass

    @abstractmethod
    def get_expected_time(
        self,
        origin: Optional[List[float]] = None,
        target: Optional[List[float]] = None,
    ) -> float:
        """
        Returns the expected time of the time model.

        Args:
            origin (Optional[List[float]], optional): The origin of the product for a transport. Defaults to None.
            target (Optional[List[float]], optional): The target of the product for a transport. Defaults to None.

        Returns:
            float: The expected time of the time model.
        """
        pass


class FunctionTimeModel(TimeModel):
    """
    Class for time models that are based on a function.

    Args:
        time_model_data (FunctionTimeModelData): The time model data object.
        statistics_buffer (List[float], optional): A buffer for the statistics. Defaults to [].
        distribution_function_object (Callable[[FunctionTimeModelData], List[float]], optional): The distribution function object. Defaults to FUNCTION_DICT[FunctionTimeModelEnum.Constant].
    """
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
        """
        Returns the next time for a time model based on a sample value of the distribution function.

        Returns:
            float: The next time of the time model.
        """
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
        """
        Returns the expected time for a time model based on the expected value of the distribution function.

        Returns:
            float: The expected time of the time model.
        """
        return self.time_model_data.location


class SequentialTimeModel(TimeModel):
    """
    Class for time models that are based on a sequence of values. A random value from the sequence is returned.

    Args:
        time_model_data (SequentialTimeModelData): The time model data object.
    """
    time_model_data: SequentialTimeModelData

    def get_next_time(
        self,
        origin: Optional[List[float]] = None,
        target: Optional[List[float]] = None,
    ) -> float:
        """
        Returns the next time for a time model based on a sample value of the sequence.

        Returns:
            float: The next time of the time model.
        """
        return np.random.choice(self.time_model_data.sequence, 1)[0]

    def get_expected_time(
        self,
        origin: Optional[List[float]] = None,
        target: Optional[List[float]] = None,
    ) -> float:
        return sum(self.time_model_data.sequence) / len(self.time_model_data.sequence)


class ManhattanDistanceTimeModel(TimeModel):
    """
    Class for time models that are based on the manhattan distance between two points and time calculation based on reaction time and speed.

    Args:
        time_model_data (ManhattanDistanceTimeModelData): The time model data object.
    """
    time_model_data: ManhattanDistanceTimeModelData

    def get_next_time(
        self,
        origin: Optional[List[float]] = None,
        target: Optional[List[float]] = None,
    ) -> float:
        """
        Returns the next time for a time model based on the manhattan distance between two points and time calculation based on reaction time and speed.

        Args:
            origin (Optional[List[float]], optional): The origin of the product for a transport. Defaults to None.
            target (Optional[List[float]], optional): The target of the product for a transport. Defaults to None.

        Returns:
            float: The next time of the time model.
        """
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
        """
        Returns the expected time for a time model based on the manhattan distance between two points and time calculation based on reaction time and speed.

        Args:
            origin (Optional[List[float]], optional): The origin of the product for a transport. Defaults to None.
            target (Optional[List[float]], optional): The target of the product for a transport. Defaults to None.

        Returns:
            float: The expected time of the time model.
        """
        if origin is None or target is None:
            raise ("Origin and target must be defined for ManhattanDistanceTimeModel")  # type: ignore
        return self.get_next_time(origin, target)


TIME_MODEL = Union[SequentialTimeModel, ManhattanDistanceTimeModel, FunctionTimeModel]
"""
Union type for all time models.
"""
