from __future__ import annotations

from typing import Optional, Union

from prodsys.models.core_asset import CoreAsset
from pydantic import conlist, validator


class QueueData(CoreAsset):
    """
    Class that represents a queue. If capacity is 0, the queue is considered infinite. Otherwise, the queue can hold a finite number of products cooresponding to the capacity.

    Args:
        ID (str): ID of the queue.
        description (str): Description of the queue.
        capacity (Union[int, float]): Capacity of the queue. If 0, the queue is considered infinite. Otherwise, the queue can hold a finite number of products cooresponding to the capacity.

    Examples:
        A finite queue with ID "Q1", description "Queue 1" and capacity 10:
        ``` py
        import prodsys
        prodsys.queue_data.QueueData(
            ID="Q1",
            description="Queue 1",
            capacity=10,
        )
        ```
        An infinite queue with ID "Q1", description "Queue 1" and capacity 0:
        ``` py
        import prodsys
        prodsys.queue_data.QueueData(
            ID="Q1",
            description="Queue 1",
            capacity=0,
        )
        ```
    """

    capacity: Union[int, float] = 0.0

    class Config:
        schema_extra = {
            "examples": [
                {
                    "ID": "Q1",
                    "description": "Finte Queue",
                    "capacity": 10,
                },
                {
                    "ID": "Q1",
                    "description": "Infinite Queue",
                    "capacity": 0.0,
                },
            ]
        }


class StorageData(QueueData):
    """
    Represents storage data for the auxiliaries.

    Attributes:
        location (List[float]): The location of the storage in 2D coordinates.
    """

    location: conlist(float, min_items=2, max_items=2) # type: ignore

    class Config:
        schema_extra = {
            "examples": [
                {
                    "ID": "S1",
                    "description": "Storage 1",
                    "capacity": 100,
                    "location": [1.0, 2.0],
                },
                {
                    "ID": "S2",
                    "description": "Storage 2",
                    "capacity": 0.0,
                    "location": [3.0, 4.0],
                },
            ]
        }