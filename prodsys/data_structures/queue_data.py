from __future__ import annotations

from typing import Union

from prodsys.data_structures.core_asset import CoreAsset
from pydantic import validator


class QueueData(CoreAsset):
    """
    Class that represents a queue. If capacity is 0, the queue is considered infinite. Otherwise, the queue can hold a finite number of materials cooresponding to the capacity.

    Args:
        ID (str): ID of the queue.
        description (str): Description of the queue.
        capacity (Union[int, float]): Capacity of the queue. If 0, the queue is considered infinite. Otherwise, the queue can hold a finite number of materials cooresponding to the capacity.

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
            "examples": {
                "Finite Queue": {
                    "summary": "Finite Queue",
                    "value": {
                        "ID": "Q1",
                        "description": "Queue 1",
                        "capacity": 10,
                    },
                },
                "Infinite Queue": {
                    "summary": "Infinite Queue",
                    "value": {
                        "ID": "Q1",
                        "description": "Queue 1",
                        "capacity": 0.0,
                    },
                },
            }
        }
