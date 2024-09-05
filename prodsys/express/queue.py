from typing import Optional, Union
from prodsys.express import core
from prodsys.models import queue_data


from pydantic import Field, conlist
from pydantic.dataclasses import dataclass


from uuid import uuid1


@dataclass
class Queue(core.ExpressObject):
        """
        Represents a storage object for auxiliaries. If an auxiliary is not needed it is always transported back to the storage.

        Attributes:
                location (List[float]): The location coordinates of the storage.
                ID (Optional[str]): The unique identifier of the storage.
                capacity (Union[int, float]): The capacity of the storage.
        """

        location: conlist(float, min_length=2, max_length=2) # type: ignore
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
                        location=self.location,
                )