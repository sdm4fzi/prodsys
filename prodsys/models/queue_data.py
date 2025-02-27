from typing import Union, Optional
from hashlib import md5

from pydantic import ConfigDict

from prodsys.models.core_asset import CoreAsset, InOutLocatable


class QueueData(CoreAsset):
    """
    Class that represents a queue for products at a resource / sink / source. If capacity is 0, the queue is considered infinite. Otherwise, the queue can hold a finite number of products cooresponding to the capacity.

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

    def hash(self) -> str:
        """
        Returns a unique hash for the queue considering its capacity.


        Returns:
            str: Hash of the queue.
        """
        return md5((str(self.capacity)).encode("utf-8")).hexdigest()

    model_config = ConfigDict(
        json_schema_extra={
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
    )


class StoreData(QueueData, InOutLocatable):
    """
    Class that represents a store which is a queue with a loctation independent of a resource / source / sink.

    If capacity is 0, the queue is considered infinite. Otherwise, the queue can hold a finite number of products cooresponding to the capacity.

    Args:
        ID (str): ID of the queue.
        description (str): Description of the queue.
        capacity (Union[int, float]): Capacity of the queue. If 0, the queue is considered infinite. Otherwise, the queue can hold a finite number of products cooresponding to the capacity.
        location (List[float]): Location of the queue. It has to be a list of length 2.
        input_location (Optional[List[float]], optional): Input location of the queue. Defaults to None.
        output_location (Optional[List[float]], optional): Output location of the queue. Defaults to None.

    Examples:
        A finite store with ID "Q1", description "Store Q1" and capacity 10:
        ``` py
        import prodsys
        prodsys.queue_data.StoreData(
            ID="Q1",
            description="Queue 1",
            capacity=10,
            location=[10, 0],
        )
        ```
        An infinite queue with ID "Q1", description "Queue 1" and capacity 0:
        ``` py
        import prodsys
        prodsys.queue_data.StoreData(
            ID="Q1",
            description="Queue 1",
            capacity=0,
            location=[10, 0],
            input_location=[11, 0],
            output_location=[12, 0],
        )
        ```
    """

    def hash(self) -> str:
        """
        Returns a unique hash for the queue considering its capacity.


        Returns:
            str: Hash of the queue.
        """
        queue_hash = QueueData.hash(self)
        location_hash = InOutLocatable.hash(self)
        return md5((location_hash + queue_hash).encode("utf-8")).hexdigest()

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ID": "Q1",
                    "description": "Finite Store",
                    "capacity": 10,
                    "location": [10, 0],
                },
                {
                    "ID": "Q1",
                    "description": "Infinite Store",
                    "capacity": 0.0,
                    "location": [10, 0],
                    "input_location": [11, 0],
                    "output_location": [12, 0],
                },
            ]
        }
    )


QUEUE_DATA_UNION = Union[QueueData, StoreData]
