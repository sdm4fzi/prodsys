from abc import ABC, abstractmethod
import itertools
from typing import Callable, Iterator, List, Optional, Tuple, Union
from typing_extensions import deprecated

import numpy as np

from prodsys.models.time_model_data import (
    FunctionTimeModelData,
    SampleTimeModelData,
    ScheduledTimeModelData,
    DistanceTimeModelData,
    TIME_MODEL_DATA,
)
from prodsys.util.statistical_functions import FUNCTION_DICT, FunctionTimeModelEnum


class TimeModel(ABC):
    """
    Abstract base class for time models.
    """

    def __init__(self, data: TIME_MODEL_DATA):
        """
        Initializes the time model with the given time model data.

        Args:
            time_model_data (TIME_MODEL_DATA): The time model data object.
        """
        self.data = data

    @abstractmethod
    def get_next_time(
        self,
        origin: Optional[List[float]] = None,  # TOOO: rework this with kwargs
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

    def __init__(
        self,
        time_model_data: FunctionTimeModelData,
    ):
        """
        Initializes the function time model with the given time model data.

        Args:
            time_model_data (FunctionTimeModelData): The time model data object.
        """
        super().__init__(time_model_data)
        self.statistics_buffer = []
        self._fill_buffer()

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
        distribution_function = FUNCTION_DICT[self.data.distribution_function]
        self.statistics_buffer = distribution_function(self.data)

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
        return self.data.location


class SampleTimeModel(TimeModel):
    """
    Class for time models that are based on a sample of values. A random value from the sample is returned.

    Args:
        time_model_data (SampleTimeModelData): The time model data object.
    """

    def __init__(self, time_model_data: SampleTimeModelData):
        """
        Initializes the sample time model with the given time model data.

        Args:
            time_model_data (SampleTimeModelData): The time model data object.
        """
        super().__init__(time_model_data)

    def get_next_time(
        self,
        origin: Optional[List[float]] = None,
        target: Optional[List[float]] = None,
    ) -> float:
        """
        Returns the next time for a time model based on a sample value of the samples.

        Returns:
            float: The next time of the time model.
        """
        return np.random.choice(self.data.samples, 1)[0]

    def get_expected_time(
        self,
        origin: Optional[List[float]] = None,
        target: Optional[List[float]] = None,
    ) -> float:
        return sum(self.data.samples) / len(self.data.samples)


class ScheduledTimeModel(TimeModel):
    """
    Class for time models that are based on a schedule of values. A value from the schedule is returned based on the current schedule state.

    Args:
        time_model_data (ScheduledTimeModelData): The time model data object.
    """

    def __init__(
        self,
        time_model_data: ScheduledTimeModelData,
    ):
        """
        Initializes the scheduled time model with the given time model data.

        Args:
            time_model_data (ScheduledTimeModelData): The time model data object.
        """
        super().__init__(time_model_data)
        self._time_value_iterator = self._get_time_value_iterator()

    def _get_time_value_iterator(self) -> Iterator[float]:
        """
        Returns an iterator for the time values of the schedule.

        Returns:
            Iterator[float]: The iterator for the time values of the schedule.
        """
        schedule = self.data.schedule
        if self.data.absolute:
            relative_schedule = [schedule[0]] + [
                schedule[i] - schedule[i - 1] for i in range(1, len(schedule))
            ]
        else:
            relative_schedule = schedule
        if self.data.cyclic:
            return itertools.cycle(relative_schedule)
        return iter(relative_schedule)

    def get_next_time(
        self,
        origin: Optional[List[float]] = None,
        target: Optional[List[float]] = None,
    ) -> float:
        """
        Returns the next time for a time model based on a schedule value of the schedule.

        Returns:
            float: The next time of the time model.
        """
        try:
            return next(self._time_value_iterator)
        except StopIteration:
            return -1

    def get_expected_time(
        self,
        origin: Optional[List[float]] = None,
        target: Optional[List[float]] = None,
    ) -> float:
        """
        Returns the expected time for a time model based on the mean time difference value of the schedule.

        Args:
            origin (Optional[List[float]], optional): Not used. Defaults to None.
            target (Optional[List[float]], optional): Not used. Defaults to None.

        Returns:
            float: The expected time of the time model.
        """
        if self.data.absolute:
            schedule = self.data.schedule
            relative_schedule = [schedule[0]] + [
                schedule[i] - schedule[i - 1] for i in range(1, len(schedule))
            ]
        else:
            relative_schedule = self.data.schedule
        return sum(relative_schedule) / len(relative_schedule)


class DistanceTimeModel(TimeModel):
    """
    Class for time models that are based on a distance between two points and time calculation based on reaction time and speed and distance metric.

    Args:
        time_model_data (DistanceTimeModelData): The time model data object.
    """

    def __init__(self, time_model_data: DistanceTimeModelData):
        """
        Initializes the distance time model with the given time model data.

        Args:
            time_model_data (DistanceTimeModelData): The time model data object.
        """
        super().__init__(time_model_data)

    def calculate_distance(self, origin: List[float], target: List[float]) -> float:
        """
        Calculate the distance between two points.

        Args:
            origin (List[float]): The origin point.
            target (List[float]): The target point.

        Returns:
            float: The distance between the two points.
        """
        if self.data.metric == "euclidean":
            return np.linalg.norm(np.array(origin) - np.array(target))
        elif self.data.metric == "manhattan":
            return np.sum(np.abs(np.array(origin) - np.array(target)))
        else:
            raise ValueError(f"Unknown distance metric: {self.data.metric}")

    def get_next_time(
        self,
        origin: Optional[List[float]] = None,
        target: Optional[List[float]] = None,
    ) -> float:
        """
        Returns the next time for a time model based on the distance between two points and time calculation based on reaction time and speed.

        Args:
            origin (Optional[List[float]], optional): The origin of the product for a transport. Defaults to None.
            target (Optional[List[float]], optional): The target of the product for a transport. Defaults to None.

        Returns:
            float: The next time of the time model.
        """
        if origin is None or target is None:
            raise ValueError("Origin and target must be defined for DistanceTimeModel")
        distance = self.calculate_distance(origin, target)
        return distance / self.data.speed + self.data.reaction_time

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
        return self.get_next_time(origin, target)


TIME_MODEL = Union[
    SampleTimeModel,
    ScheduledTimeModel,
    DistanceTimeModel,
    FunctionTimeModel,
]
"""
Union type for all time models.
"""
