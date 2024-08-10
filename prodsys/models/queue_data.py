from typing import Union, Optional
from hashlib import md5

from pydantic import ConfigDict, conlist

from prodsys.models.core_asset import CoreAsset


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
    #TODO: add optional location of queue for warehousing
    capacity: Union[int, float] = 0.0
    location: Optional[conlist(float, min_length=2, max_length=2)] = None # type: ignore

    def hash(self) -> str:
        """
        Returns a unique hash for the queue considering its capacity.


        Returns:
            str: Hash of the queue.
        """
        return md5((str(self.capacity)).encode("utf-8")).hexdigest()

    model_config=ConfigDict(json_schema_extra={
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
    
    })