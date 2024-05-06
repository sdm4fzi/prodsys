"""
The `time_model` module contains classes to specify time models in the simulation for the arrival
of products, performance of processes and the duration of states.

The following time models are possible:
- `SequentialTimeModel`: A time model that is based on a sequence of values.
- `FunctionTimeModel`: A time model that is based on a distribution function which gets sampled.
- `ManhattanDistanceTimeModel`: A time model that is based on the manhattan distance between two nodes and a constant velocity.
"""
from __future__ import annotations

from typing import List, Literal, Optional, Union
from typing_extensions import deprecated
from uuid import uuid1

from pydantic.dataclasses import dataclass
from pydantic import Field

from prodsys.models import time_model_data
from prodsys.express import core

@deprecated(
    "The SequentialTimeModel is deprecated and will be removed in the next version. Please use the SampleTimeModel instead.",
    category=None
)
@dataclass
class SequentialTimeModel(core.ExpressObject):
    """
    Class that represents a time model that is based on a sequence of values.

    Args:
        sequence (List[float]): Sequence of time values.
        ID (str): ID of the time model.

    Examples:
        Sequential time model with 7 time values:
        ``` py
        import prodsys.express as psx
        psx.SequentialTimeModel(
            sequence=[25.0, 13.0, 15.0, 16.0, 17.0, 20.0, 21.0],
        )
        ```
    """
    sequence: List[float]
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))


    def to_model(self) -> time_model_data.SequentialTimeModelData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            time_model_data.SequentialTimeModelData: Data object of the express object.
        """
        return time_model_data.SequentialTimeModelData(
            sequence=self.sequence,
            ID=self.ID,
            description=""
        )
    
@dataclass
class SampleTimeModel(core.ExpressObject):
    """
    Class that represents a time model that is based on a list of sample values.

    Args:
        samples (List[float]): Values to sample from.
        ID (str): ID of the time model.

    Examples:
        Sample time model with 7 time values:
        ``` py
        import prodsys.express as psx
        psx.SampleTimeModel(
            samples=[25.0, 13.0, 15.0, 16.0, 17.0, 20.0, 21.0],
        )
        ```
    """
    samples: List[float]
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))


    def to_model(self) -> time_model_data.SampleTimeModelData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            time_model_data.SequentialTimeModelData: Data object of the express object.
        """
        return time_model_data.SampleTimeModelData(
            samples=self.samples,
            ID=self.ID,
            description=""
        )
    
@dataclass
class ScheduledTimeModel(core.ExpressObject):
    """
    Class that represents a time model that is based on a schedule of timely values.
    If the schedule is not cyclic, usage in other classes than sources can lead to unexpected behavior.

    Args:
        schedule (List[float]): Schedule of time values.
        absolute (bool): If the schedule contains absolute time values or relative values to each other.
        cyclic (bool): If the schedule is cyclic or not.
        ID (str): ID of the time model.

    Examples:
        Scheduled time model with 7 time values:
        ``` py
        import prodsys.express as psx
        psx.ScheduledTimeModel(
            schedule=[25.0, 13.0, 15.0, 16.0, 17.0, 20.0, 21.0],
        )
        ```
    """
    schedule: List[float]
    absolute: bool = True
    cyclic: bool = True
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))


    def to_model(self) -> time_model_data.ScheduledTimeModelData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            time_model_data.SequentialTimeModelData: Data object of the express object.
        """
        return time_model_data.ScheduledTimeModelData(
            schedule=self.schedule,
            absolute=self.absolute,
            cyclic=self.cyclic,
            ID=self.ID,
            description=""
        )

@dataclass
class FunctionTimeModel(core.ExpressObject):
    """
    Class that represents a time model that is based on a function and represents the timely values by their distribution function.

    Args:
        distribution_function (FunctionTimeModelEnum): Function that represents the time model, can either be 'normal', 'lognormal', 'exponential' or 'constant'.
        location (float): Location parameter of the distribution function.
        scale (float): Scale parameter of the distribution function.
        ID (str): ID of the time model.


    Examples:
        Normal distribution time model with 20 minutes mean and 5 minutes standard deviation:
        ``` py
        import prodsys.express as psx
        psx.FunctionTimeModel(
            distribution_function="normal",
            location=20.0,
            scale=5.0,
        )
        ```
    """
    distribution_function: time_model_data.FunctionTimeModelEnum
    location: float
    scale: float = 0.0
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def to_model(self) -> time_model_data.FunctionTimeModelData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            time_model_data.FunctionTimeModelData: Data object of the express object.
        """
        return time_model_data.FunctionTimeModelData(
            distribution_function=self.distribution_function,
            location=self.location,
            scale=self.scale,
            ID=self.ID,
            description=""
        )
    

@dataclass
class DistanceTimeModel(core.ExpressObject):
    """
    Class that represents a time model that is based on the distance between two nodes and a constant velocity.
    The distance is calculated by the specified distance metric.

    Args:
        speed (float): Speed of the vehicle in meters per minute.
        reaction_time (float): Reaction time of the driver in minutes.
        metric (Literal["manhattan", "euclidean"]): Metric to calculate the distance.

    Examples:
        Distance time model with a speed of 50 meters per minute and a reaction time of 0.5 minutes, using the default manhattan distance metric:
        ``` py
        import prodsys.express as psx
        psx.DistanceTimeModel(
            speed=50.0,
            reaction_time=0.5,
        )
        ```
    """
    speed: float
    reaction_time: float
    metric: Literal["manhattan", "euclidean"] = "manhattan"
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def to_model(self) -> time_model_data.DistanceTimeModelData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            time_model_data.DistanceTimeModelData: Data object of the express object.
        """
        return time_model_data.DistanceTimeModelData(
            speed=self.speed,
            reaction_time=self.reaction_time,
            metric=self.metric,
            ID=self.ID,
            description=""
        )

@deprecated(
    "The ManhattanDistanceTimeModel is deprecated and will be removed in the next version. Please use the DistanceTimeModel instead.",
    category=None
)
@dataclass
class ManhattanDistanceTimeModel(core.ExpressObject):
    """
    Class that represents a time model that is based on the manhattan distance between two nodes and a constant velocity.

    Args:
        speed (float): Speed of the vehicle in meters per minute.
        reaction_time (float): Reaction time of the driver in minutes.

    Examples:
        Manhattan distance time model with a speed of 50 meters per minute and a reaction time of 0.5 minutes:
        ``` py
        import prodsys.express as psx
        psx.ManhattenDistanceTimeModel(
            speed=50.0,
            reaction_time=0.5,
        )
        ```
    """
    speed: float
    reaction_time: float
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def to_model(self) -> time_model_data.ManhattanDistanceTimeModelData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            time_model_data.ManhattanDistanceTimeModelData: Data object of the express object.
        """
        return time_model_data.ManhattanDistanceTimeModelData(
            speed=self.speed,
            reaction_time=self.reaction_time,
            ID=self.ID,
            description=""
        )

TIME_MODEL_UNION = Union[
    SampleTimeModel,
    ScheduledTimeModel,
    DistanceTimeModel,
    FunctionTimeModel,
    SequentialTimeModel,
    ManhattanDistanceTimeModel,
]
    



