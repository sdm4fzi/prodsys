from typing import Optional, Union
from prodsys.express import core
from prodsys.models import queue_data


from pydantic import Field, conlist
from pydantic.dataclasses import dataclass


from uuid import uuid1


@dataclass
class Queue(core.ExpressObject):
    """
    Represents a storage object for products. A queue has no location, but is part of a resource / source / sink and has the same location as the resource / source / sink.

    The capacity of the queue is the maximum number of products that can be stored in the queue.

    Attributes:
            ID (Optional[str]): The unique identifier of the storage.
            capacity (Union[int, float]): The capacity of the storage.
    """

    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))
    capacity: Union[int, float] = 0

    def to_model(self) -> queue_data.QueueData:
        """
        Converts the storage object to a `StorageData` model.

        Returns:
                StorageData: The converted storage data.
        """
        return queue_data.QueueData(
            ID=self.ID,
            description="",
            capacity=self.capacity,
        )


@dataclass
class Store(Queue):
    """
    A store is a storage object for products / auiliaries. It has a location, an input location, and an output location. The input location is the location where products are stored, and the output location is the location where products are retrieved.

    A store can be understood as queue that is independent of a resource / source / sink concerning its location.

    Attributes:
            location (List[float]): The location coordinates of the storage.
            input_location (Optional[List[float]]): The input location coordinates of the storage.
            output_location (Optional[List[float]]): The output location coordinates of the storage.
            ID (Optional[str]): The unique identifier of the storage.
            capacity (Union[int, float]): The capacity of the storage.
    """

    location: list[float] = Field(..., min_length=2, max_length=2)
    input_location: Optional[list[float]] = Field(None, min_length=2, max_length=2)
    output_location: Optional[list[float]] = Field(None, min_length=2, max_length=2)
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))
    capacity: Union[int, float] = 0

    def to_model(self) -> queue_data.StoreData:
        """
        Converts the storage object to a `StorageData` model.

        Returns:
                StorageData: The converted storage data.
        """
        return queue_data.StoreData(
            ID=self.ID,
            description="",
            capacity=self.capacity,
            location=self.location,
            input_location=self.input_location,
            output_location=self.output_location,
        )
