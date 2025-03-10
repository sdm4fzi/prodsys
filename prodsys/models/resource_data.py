"""
In `prodsys` exist two different types of resources: production resources and transport resources. Production resources are resources that can perform processes on products. Transport resources are resources that can transport products from one location to another. Both types of resources are represented by the `ResourceData` class. The `ResourceData` class is an abstract base class and cannot be instantiated. Instead, the `ProductionResourceData` and `TransportResourceData` classes can be used to represent production resources and transport resources, respectively.

The following resources are available:

- `ProductionResourceData`: Class that represents a production resource.
- `TransportResourceData`: Class that represents a transport resource.
"""

from __future__ import annotations
from hashlib import md5
from typing import Any, Literal, Union, List, Optional, TYPE_CHECKING
from enum import Enum

from pydantic import (
    ConfigDict,
    ValidationInfo,
    field_validator,
    model_validator,
    conlist,
)
from prodsys.models.core_asset import CoreAsset, InOutLocatable, Locatable

if TYPE_CHECKING:
    from prodsys.adapters.adapter import ProductionSystemAdapter


class ControllerEnum(str, Enum):
    """
    Enum that represents the controller of a resource.

    - PipelineController: Pipeline controller.
    - TransportController: Transport controller.
    - BatchController: Batch controller.
    """

    PipelineController = "PipelineController"
    TransportController = "TransportController"
    BatchController = "BatchController"


class ResourceControlPolicy(str, Enum):
    """
    Enum that represents the control policy of a resource.

    - FIFO: First in first out.
    - LIFO: Last in first out.
    - SPT: Shortest processing time first.
    """

    FIFO = "FIFO"
    LIFO = "LIFO"
    SPT = "SPT"


class TransportControlPolicy(str, Enum):
    """
    Enum that represents the control policy of a transport resource.

    - FIFO: First in first out.
    - SPT_transport: Shortest raw transport time first. Does not consider distance to start of the transport.
    - NEAREST_ORIGIN_AND_LONGEST_TARGET_QUEUES_TRANSPORT: Nearest_Origin but also sorts by the length of the target queue to make sure, something can be picked up at the target.
    - NEAREST_ORIGIN_AND_SHORTEST_TARGET_INPUT_QUEUES_TRANSPORT: Nearest_Origin but also sorts by the length of the target input queue to prefer target machines, that have lower number of products waiting to be processed.
    """

    FIFO = "FIFO"
    SPT_transport = "SPT_transport"
    NEAREST_ORIGIN_AND_LONGEST_TARGET_QUEUES_TRANSPORT = (
        "Nearest_origin_and_longest_target_queues_transport"
    )
    NEAREST_ORIGIN_AND_SHORTEST_TARGET_INPUT_QUEUES_TRANSPORT = (
        "Nearest_origin_and_shortest_target_input_queues_transport"
    )


class ResourceData(CoreAsset, Locatable):
    """
    Class that represents resource data. Base class for ProductionResourceData and TransportResourceData.

    Args:
        ID (str): ID of the resource.
        description (str): Description of the resource.
        capacity (int): Capacity of the resource.
        location (List[float]): Location of the resource. Has to be a list of length 2.
        controller (ControllerEnum): Controller of the resource.
        control_policy (Union[ResourceControlPolicy, TransportControlPolicy]): Control policy of the resource.
        process_ids (List[str]): Process IDs of the resource.
        process_capacities (Optional[List[int]], optional): Process capacities of the resource (in sequence of the capacity of the resource). Defaults to None.
        state_ids (Optional[List[str]], optional): State IDs of the resource. Defaults to [].
    """

    capacity: int

    controller: ControllerEnum
    control_policy: Union[ResourceControlPolicy, TransportControlPolicy]

    process_ids: List[str]
    process_capacities: Optional[List[int]]
    state_ids: Optional[List[str]] = []

    @model_validator(mode="before")
    def check_process_capacity(cls, values):
        if not isinstance(values, dict):
            return values
        if not "process_capacities" in values or values["process_capacities"] is None:
            values["process_capacities"] = [
                values["capacity"] for _ in values["process_ids"]
            ]
        if len(values["process_capacities"]) != len(values["process_ids"]):
            raise ValueError(
                f"process_capacities {values['process_capacities']} must have the same length as processes {values['process_ids']}"
            )
        if values["process_capacities"] and max(values["process_capacities"]) > values["capacity"]:
            raise ValueError("process_capacities must be smaller than capacity")
        return values

    def hash(self, adapter: ProductionSystemAdapter) -> str:
        """
        Returns a unique hash of the resource considering the capacity, location (input/output for production resources or location for transport resources),
        controller, processes, process capacities, and states. Can be used to compare resources for equal functionality.

        Args:
            adapter (ProductionSystemAdapter): Adapter that contains the process and state data.

        Raises:
            ValueError: If a state or process is not found in the adapter.

        Returns:
            str: Hash of the resource.
        """
        state_hashes = []
        process_hashes = []

        base_class_hash = Locatable.hash(self)

        for state_id in self.state_ids:
            for state in adapter.state_data:
                if state.ID == state_id:
                    state_hashes.append(state.hash(adapter))
                    break
            else:
                raise ValueError(
                    f"State with ID {state_id} not found for resource {self.ID}."
                )

        for process_id in self.process_ids:
            for process in adapter.process_data:
                if process.ID == process_id:
                    process_hashes.append(process.hash(adapter))
                    break
            else:
                raise ValueError(
                    f"Process with ID {process_id} not found for resource {self.ID}."
                )

        return md5(
            (
                "".join(
                    [
                        base_class_hash,
                        str(self.capacity),
                        self.controller,
                        *sorted(process_hashes),
                        *map(str, self.process_capacities),
                        *sorted(state_hashes),
                    ]
                )
            ).encode("utf-8")
        ).hexdigest()


class ProductionResourceData(ResourceData, InOutLocatable):
    """
    Class that represents production resource data.

    Args:
        ID (str): ID of the resource.
        description (str): Description of the resource.
        capacity (int): Capacity of the resource.
        location (List[float]): Location of the resource. Has to be a list of length 2.
        input_location (Optional[List[float]]): Input location of the resource. Has to be a list of length 2.
        output_location (Optional[List[float]]): Output location of the resource. Has to be a list of length 2.
        controller (ControllerEnum): Controller of the resource.
        control_policy (ResourceControlPolicy): Control policy of the resource.
        process_ids (List[str]): Process IDs of the resource.
        process_capacities (Optional[List[int]], optional): Process capacities of the resource. Defaults to None.
        state_ids (Optional[List[str]], optional): State IDs of the resource. Defaults to [].
        input_queues (Optional[List[str]], optional): Input queues of the resource. Defaults to None.
        output_queues (Optional[List[str]], optional): Output queues of the resource. Defaults to None.

    Examples:
        Creation of a production resource with a capacity of 2, a location of [10.0, 10.0], a PipelineController and a FIFO control policy:
        ```py
        import prodsys
        prodsys.resource_data.ProductionResourceData(
            ID="R1",
            description="Resource 1",
            capacity=2,
            location=[10.0, 10.0],
            controller=prodsys.resource_data.ControllerEnum.PipelineController,
            control_policy=prodsys.resource_data.ResourceControlPolicy.FIFO,
            process_ids=["P1", "P2"],
            process_capacities=[2, 1],
            states=[
                "Breakdownstate_1",
                "Setup_State_1",
            ],
            input_queues=["IQ1"],
            output_queues=["OQ1"],
        )
        ```
    """

    controller: Literal[
        ControllerEnum.PipelineController, ControllerEnum.BatchController
    ]
    control_policy: ResourceControlPolicy
    input_queues: List[str] = []
    output_queues: List[str] = []
    batch_size: Optional[int] = None

    @model_validator(mode="before")
    def validate_batch_size(cls, data: Any):
        if not isinstance(data, dict):
            return data
        if ("batch_size" in data and data["batch_size"] is not None) and data[
            "controller"
        ] != ControllerEnum.BatchController:
            raise ValueError(
                "Batch size can only be set for resources with a BatchController."
            )
        if ("batch_size" not in data or data["batch_size"] is None) and data[
            "controller"
        ] == ControllerEnum.BatchController:
            raise ValueError(
                "Batch size has to be set for resources with a BatchController."
            )
        if ("batch_size" in data and data["batch_size"] is not None) and data[
            "batch_size"
        ] > data["capacity"]:
            raise ValueError(
                "Batch size cannot be greater than the capacity of the resource."
            )
        return data

    def hash(self, adapter: ProductionSystemAdapter) -> str:
        """
        Returns a unique hash of the resource considering the capacity, location, controller, processes, process capacities, states, input queues and output queues. Can be used to compare resources for equal functionality.

        Args:
            adapter (ProductionSystemAdapter): Adapter that contains the process and queue data.

        Raises:
            ValueError: If a queue, state or process is not found in the adapter.

        Returns:
            str: Hash of the resource.
        """
        base_class_hash = ResourceData.hash(self, adapter) + InOutLocatable.hash(self)
        queue_hashes = []
        for queue_id in self.input_queues + self.output_queues:
            for queue in adapter.queue_data:
                if queue.ID == queue_id:
                    queue_hashes.append(queue.hash())
                    break
            else:
                raise ValueError(
                    f"Queue with ID {queue_id} not found for resource {self.ID}."
                )

        return md5(
            ("".join([base_class_hash, *sorted(queue_hashes)])).encode("utf-8")
        ).hexdigest()

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ID": "R1",
                    "description": "Resource 1",
                    "capacity": 2,
                    "location": [10.0, 10.0],
                    "controller": "PipelineController",
                    "control_policy": "FIFO",
                    "process_ids": ["P1", "P2"],
                    "process_capacities": [2, 1],
                    "states": [
                        "Breakdownstate_1",
                        "Setup_State_1",
                    ],
                    "input_queues": ["IQ1"],
                    "output_queues": ["OQ1"],
                }
            ]
        }
    )


class TransportResourceData(ResourceData):
    """
    Class that represents transport resource data.

    Args:
        ID (str): ID of the resource.
        description (str): Description of the resource.
        capacity (int): Capacity of the resource.
        location (List[float]): Location of the resource. Has to be a list of length 2.
        controller (Literal[ControllerEnum.TransportController]): Controller of the resource, has to be a TransportController.
        control_policy (TransportControlPolicy): Control policy of the resource.
        process_ids (List[str]): Process IDs of the resource.
        process_capacities (Optional[List[int]], optional): Process capacities of the resource. Defaults to None.
        state_ids (Optional[List[str]], optional): State IDs of the resource. Defaults to [].

    Examples:
        Creation of a transport resource with a capacity of 1, a location of [15.0, 15.0], a TransportController and a FIFO control policy:
        ```py
        import prodsys
        prodsys.resource_data.TransportResourceData(
            ID="TR1",
            description="Transport Resource 1",
            capacity=1,
            location=[15.0, 15.0],
            controller=prodsys.resource_data.ControllerEnum.TransportController,
            control_policy=prodsys.resource_data.TransportControlPolicy.FIFO,
            process_ids=["TP1"],
        )
        ```
    """

    controller: Literal[ControllerEnum.TransportController]
    control_policy: TransportControlPolicy

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ID": "TR1",
                    "description": "Transport Resource 1",
                    "capacity": 1,
                    "location": [15.0, 15.0],
                    "controller": "TransportController",
                    "control_policy": "FIFO",
                    "process_ids": ["TP1"],
                    "process_capacities": None,
                    "states": ["Breakdownstate_1"],
                },
            ]
        }
    )


RESOURCE_DATA_UNION = Union[ProductionResourceData, TransportResourceData]
