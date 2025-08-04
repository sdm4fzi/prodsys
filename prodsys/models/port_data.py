from enum import Enum
from typing import Union, Optional
from hashlib import md5

from pydantic import ConfigDict, Field

from prodsys.models.core_asset import CoreAsset, Locatable, Location2D

class PortInterfaceType(Enum):
    """
    Enum that represents the type of an interface.
    """
    INPUT = "input"
    OUTPUT = "output"
    INPUT_OUTPUT = "input_output"

class PortType(Enum):
    """
    Enum that represents the kind of an interface.
    """
    QUEUE = "queue"
    STORE = "store"


class QueueData(CoreAsset):
    """
    Class that represents a queue for products at a resource / sink / source. If capacity is 0, the queue is considered infinite. Otherwise, the queue can hold a finite number of products cooresponding to the capacity.

    Args:
        ID (str): ID of the queue.
        description (str): Description of the queue.
        capacity (Union[int, float]): Capacity of the queue. If 0, the queue is considered infinite. Otherwise, the queue can hold a finite number of products cooresponding to the capacity.
        location (List[float]): Location of the queue. It has to be a list of length 2. If not provided, the position is inferred from the parent resource. Defaults to None.
    
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
    location: Optional[Location2D] = Field(
        default=None,
    )
    interface_type: PortInterfaceType = PortInterfaceType.INPUT_OUTPUT
    port_type: PortType = Field(default=PortType.QUEUE, init=False, frozen=True)

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


class StoreData(QueueData):
    """
    Class that represents a store which is a storage with multiple input and output port locations.

    If capacity is 0, the store is considered infinite. Otherwise, the queue can hold a finite number of products cooresponding to the capacity.

    Args:
        ID (str): ID of the store.
        description (str): Description of the store.
        capacity (Union[int, float]): Capacity of the store. If 0, the queue is considered infinite. Otherwise, the queue can hold a finite number of products cooresponding to the capacity.
        location (List[float]): Location of the store. It has to be a list of length 2.
        port_locations (Optional[list[list[float]]], optional): List of port locations for input and output. Each port location has to be a list of length 2. Defaults to None.

    Examples:
        A finite store with ID "ST1", description "Store Q1" and capacity 10:
        ``` py
        import prodsys
        prodsys.queue_data.StoreData(
            ID="ST1",
            description="Store Q1",
            capacity=10,
            location=[10, 0],
        )
        ```
        An infinite store with ID "ST1", description "Store Q1", capacity 0 and port locations [[11, 0], [12, 0]]:
        ``` py
        import prodsys
        prodsys.queue_data.StoreData(
            ID="ST1",
            description="Store Q1",
            capacity=0,
            location=[10, 0],
            port_locations=[[11, 0], [12, 0]],
        )
        ```
    """
    port_locations: Optional[list[Location2D]] = Field(
        default=None,
    )
    interface_type: PortInterfaceType = PortInterfaceType.INPUT_OUTPUT
    port_type: PortType = Field(default=PortType.STORE, init=False, frozen=True)

    def hash(self) -> str:
        """
        Returns a unique hash for the queue considering its capacity.


        Returns:
            str: Hash of the queue.
        """
        queue_hash = QueueData.hash(self)
        location_hash = Locatable.hash(self)
        port_locations_hash = md5(
            (str(self.port_locations) if self.port_locations else "").encode("utf-8")
        ).hexdigest()
        return md5((location_hash + queue_hash + port_locations_hash).encode("utf-8")).hexdigest()

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
                    "port_locations": [[11, 0], [12, 0]],
                },
            ]
        }
    )


QUEUE_DATA_UNION = Union[QueueData, StoreData]
