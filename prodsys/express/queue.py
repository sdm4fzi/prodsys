from typing import Optional, Union
from prodsys.express import core
from prodsys.models import port_data


from pydantic import Field, conlist
from pydantic.dataclasses import dataclass


from uuid import uuid1

from prodsys.models.core_asset import Location2D


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
    location: Optional[Location2D] = None
    interface_type: port_data.PortInterfaceType = port_data.PortInterfaceType.INPUT_OUTPUT

    def to_model(self) -> port_data.QueueData:
        """
        Converts the storage object to a `StorageData` model.

        Returns:
                StorageData: The converted storage data.
        """
        return port_data.QueueData(
            ID=self.ID,
            description="",
            capacity=self.capacity,
            location=self.location,
            interface_type=self.interface_type,
        )


@dataclass
class Store(Queue):
    """
    A store is a storage object for products / auiliaries. It has a location, an input location, and an output location. The input location is the location where products are stored, and the output location is the location where products are retrieved.

    A store can be understood as queue that is independent of a resource / source / sink concerning its location.

    Attributes:
            location (List[float]): The location coordinates of the storage.
            port_locations (Optional[list[Location2D]]): The locations of the store ports. If not provided, the store has only one port at the location.
            ID (Optional[str]): The unique identifier of the storage.
            capacity (Union[int, float]): The capacity of the storage.
    """
    port_locations: Optional[list[Location2D]] = Field(
        default=None,
    )    
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def to_model(self) -> port_data.StoreData:
        """
        Converts the storage object to a `StorageData` model.

        Returns:
                StorageData: The converted storage data.
        """
        return port_data.StoreData(
            ID=self.ID,
            description="",
            capacity=self.capacity,
            location=self.location,
            port_locations=self.port_locations,
            interface_type=self.interface_type,
        )
