"""
The `time_model` module contains classes to specify time models in the simulation for the arrival
of products, performance of processes and transports and the duration of states.

The following time models are possible:
- `SequentialTimeModelData`: A time model that is based on a sequence of values.
- `FunctionTimeModelData`: A time model that is based on a distribution function which gets sampled.
- `ManhattanDistanceTimeModelData`: A time model that is based on the manhattan distance between two nodes and a constant velocity.
"""
# from __future__ import annotations

from hashlib import md5
from typing import List, Literal, Union
from typing_extensions import deprecated
from enum import Enum

from pydantic import ConfigDict, Field

from prodsys.models.core_asset import CoreAsset
from prodsys.util.statistical_functions import FunctionTimeModelEnum


class TimeModelEnum(str, Enum):
    """
    Enum that represents the different kind time models.

    - FunctionTimeModel: A time model that is based on a distribution function which gets sampled.
    - SampleTimeModel: A time model that samples values from a provided data set by random choice of a sample element.
    - ScheduledTimeModel: A time model that is based on a schedule of timely values. Should only be used for arrival time models of sources.
    - DistanceTimeModel: A time model that is based on the distance between two nodes and a constant velocity and a distance metric.
    - SequentialTimeModel: A time model that is based on a sequence of values. Deprecated, use SampleTimeModel instead.
    - ManhattanDistanceTimeModel: A time model that is based on the manhattan distance between two nodes and a constant velocity. Deprecated, use DistanceTimeModel instead.
    """

    FunctionTimeModel = "FunctionTimeModel"
    SampleTimeModel = "SampleTimeModel"
    ScheduledTimeModel = "ScheduledTimeModel"
    DistanceTimeModel = "DistanceTimeModel"
    # TODO: remove in the future
    SequentialTimeModel = "SequentialTimeModel"
    ManhattanDistanceTimeModel = "ManhattanDistanceTimeModel"




@deprecated(
    'prodsys SequentialTimeModelData is deprecated and will be removed in the future. '
    'Use prodsys.models.time_model_data.SampleTimeModel instead.',
    category=None,
)
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

    def hash(self) -> str:
        """
        Returns a unique hash for the time model considering its sequence. Can be used to compare time models for equal functionality.

        Returns:
            str: Hash of the time model.
        """
        return md5(("".join([*map(str, self.sequence)])).encode("utf-8")).hexdigest()
    
    model_config=ConfigDict(json_schema_extra={
        "examples": [
            {
                "ID": "sequence_time_model_1",
                "description": "Examplary sequence time model",
                "sequence": [25.0, 13.0, 15.0, 16.0, 17.0, 20.0, 21.0],
            },
        ]
    
    })


class SampleTimeModelData(CoreAsset):
    """
    Class that represents a time model that samples values from a provided data set by random choice of a sample element.

    Args:
        ID (str): ID of the time model.
        description (str): Description of the time model.
        samples (List[float]): List of sample time values.

    Examples:
        Sample time model with 7 time values:
        ```	py
        import prodsys
        prodsys.time_model_data.SampleTimeModelData(
            ID="sample_time_model_1",
            description="Examplary sample time model",
            samples=[25.0, 13.0, 15.0, 16.0, 17.0, 20.0, 21.0],
        )
        ```
    """

    samples: List[float]

    def hash(self) -> str:
        """
        Returns a unique hash for the time model considering its samples. Can be used to compare time models for equal functionality.

        Returns:
            str: Hash of the time model.
        """
        return md5(("".join([*map(str, self.samples)])).encode("utf-8")).hexdigest()
    
    model_config=ConfigDict(json_schema_extra={
        "examples": [
            {
                "ID": "sample_time_model_1",
                "description": "Examplary sample time model",
                "samples": [25.0, 13.0, 15.0, 16.0, 17.0, 20.0, 21.0],
            },
        ]
    
    })


class ScheduledTimeModelData(CoreAsset):
    """
    Class that represents a time model that is based on a schedule of timely values. Should only be used for arrival time models of sources.

    Args:
        ID (str): ID of the time model.
        description (str): Description of the time model.
        schedule (List[float]): Schedule of time values.
        absolute (bool): If the schedule contains absolute time values in simulation time or relative time differences. Default is False.
        cyclic (bool): If the schedule should be repeated cyclically. If False, the time model does not return any values after the schedule is exhausted. Default is False.

    Examples:
        Scheduled time model with 7 time values:
        ```	py
        import prodsys
        prodsys.time_model_data.ScheduledTimeModelData(
            ID="scheduled_time_model_1",
            description="Examplary scheduled time model",
            schedule=[3.0, 5.0, 7.0, 9.0, 11.0, 13.0, 15.0],
            absolute=True,
            cyclic=False
        )
        ```
    """

    schedule: List[float]
    absolute: bool
    cyclic: bool = False

    def hash(self) -> str:
        """
        Returns a unique hash for the time model considering its schedule and boolean values. Can be used to compare time models for equal functionality.

        Returns:
            str: Hash of the time model.
        """
        return md5(("".join([*map(str, self.schedule)] + [*map(str, [self.absolute, self.cyclic])])).encode("utf-8")).hexdigest()
    
    model_config=ConfigDict(json_schema_extra={
        "examples": [
            {
                "ID": "scheduled_time_model_1",
                "description": "Examplary scheduled time model",
                "schedule": [3.0, 5.0, 7.0, 9.0, 11.0, 13.0, 15.0],
                "absolute": True,
                "cyclic": False
            },
        ]
    
    })


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

    model_config=ConfigDict(json_schema_extra={
        "examples": [
            {
                "ID": "function_time_model_1",
                "description": "normal distribution time model with 20 minutes",
                "distribution_function": "normal",
                "location": 20.0,
                "scale": 5.0,
            },
        ]
    
    })
    
    def hash(self) -> str:
        """
        Returns a unique hash for the time model considering its distribution function, location and scale. Can be used to compare time models for equal functionality.

        Returns:
            str: Hash of the time model.
        """
        return md5(("".join([*map(str, [self.distribution_function, self.location, self.scale])])).encode("utf-8")).hexdigest()
    
@deprecated(
    'prodsys ManhattanDistanceTimeModelData is deprecated and will be removed in the future. Use instead the prodsys.models.time_model_data.DistanceTimeModelData.',
    category=None,
)
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

    def hash(self) -> str:
        """
        Returns a unique hash for the time model considering its speed and reaction time. Can be used to compare time models for equal functionality.

        Returns:
            str: Hash of the time model.
        """
        return md5(("".join([*map(str, [self.speed, self.reaction_time])])).encode("utf-8")).hexdigest()
    
    model_config=ConfigDict(json_schema_extra={
        "examples": [
            {
                "ID": "manhattan_time_model_1",
                "description": "manhattan time model with speed 180 m/min = 3 m/s",
                "speed": 180.0,
                "reaction_time": 0.15,
            },
        ]
    })

class DistanceTimeModelData(CoreAsset):
    """
    Class that represents a time model that is based on the distance between two nodes and a constant velocity.
    The distance is calculated based on the metric provided.

    Args:
        ID (str): ID of the time model.
        description (str): Description of the time model.
        speed (float): Speed of the transport.
        reaction_time (float): Reaction time of the transport.
        metric (Literal["manhattan", "euclidian"]): Metric to calculate the distance. Default is "manhattan".

    Examples:
        Distance time model with speed 180 m/min = 3 m/s and reaction time 0.15 minutes:
        ``` py
        import prodsys
        time_model_data.DistanceTimeModelData(
            ID="distance_time_model_1",
            description="distance time model with speed 180 m/min = 3 m/s",
            speed=180.0,
            reaction_time=0.15,
            metric="manhattan",
        )
    """

    speed: float
    reaction_time: float
    metric: Literal["manhattan", "euclidian"] = "manhattan"

    def hash(self) -> str:
        """
        Returns a unique hash for the time model considering its speed and reaction time. Can be used to compare time models for equal functionality.

        Returns:
            str: Hash of the time model.
        """
        return md5(("".join([*map(str, [self.speed, self.reaction_time, self.metric])])).encode("utf-8")).hexdigest()
    
    model_config=ConfigDict(json_schema_extra={
        "examples": [
            {
                "ID": "distance_time_model_1",
                "description": "distance time model with speed 180 m/min = 3 m/s",
                "speed": 30.0,
                "reaction_time": 0.15,
                "metric": "manhattan",
            },
        ]
    })


TIME_MODEL_DATA = Union[
    FunctionTimeModelData, SampleTimeModelData, ScheduledTimeModelData, DistanceTimeModelData, SequentialTimeModelData, ManhattanDistanceTimeModelData, 
]
