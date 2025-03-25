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


class ResourceData(CoreAsset, InOutLocatable):
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

    control_policy: Union[ResourceControlPolicy, TransportControlPolicy]

    process_ids: List[str]
    process_capacities: Optional[List[int]]
    state_ids: Optional[List[str]] = []

    controller: ControllerEnum = ControllerEnum.PipelineController
    input_queues: List[str] = []
    output_queues: List[str] = []
    batch_size: Optional[int] = None

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

    @model_validator(mode="before")
    def validate_batch_size(cls, data: Any):
        if not isinstance(data, dict):
            return data

        controller = data.get("controller")
        batch_size = data.get("batch_size")

        # Only apply batch size validation for production resources
        if batch_size is not None and controller != ControllerEnum.BatchController:
            raise ValueError(
                "Batch size can only be set for resources with a BatchController."
            )
        if batch_size is None and controller == ControllerEnum.BatchController:
            raise ValueError(
                "Batch size has to be set for resources with a BatchController."
            )
        if batch_size is not None and batch_size > data.get("capacity", 0):
            raise ValueError(
                "Batch size cannot be greater than the capacity of the resource."
            )

        return data

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
        queue_hashes = []

        base_class_hash = Locatable.hash(self) + InOutLocatable.hash(self)

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

        # For production resources, include queues in the hash
        if hasattr(self, "input_queues") and hasattr(self, "output_queues"):
            for queue_id in self.input_queues + self.output_queues:
                for queue in adapter.queue_data:
                    if queue.ID == queue_id:
                        queue_hashes.append(queue.hash())
                        break
                else:
                    raise ValueError(
                        f"Queue with ID {queue_id} not found for resource {self.ID}."
                    )

        components = [
            base_class_hash,
            str(self.capacity),
            self.controller.value,
            *sorted(process_hashes),
            *map(str, self.process_capacities or []),
            *sorted(state_hashes),
        ]

        if hasattr(self, "input_queues") and hasattr(self, "output_queues"):
            components.extend(sorted(queue_hashes))
            if self.batch_size is not None:
                components.append(str(self.batch_size))

        return md5(("".join(components)).encode("utf-8")).hexdigest()

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                # Production resource example
                {
                    "ID": "R1",
                    "description": "Production Resource",
                    "capacity": 2,
                    "location": [10.0, 10.0],
                    "controller": "PipelineController",
                    "control_policy": "FIFO",
                    "process_ids": ["P1", "P2"],
                    "process_capacities": [2, 1],
                    "state_ids": ["Breakdownstate_1"],
                    "input_queues": ["IQ1"],
                    "output_queues": ["OQ1"],
                },
                # Transport resource example
                {
                    "ID": "TR1",
                    "description": "Transport Resource",
                    "capacity": 1,
                    "location": [15.0, 15.0],
                    "controller": "TransportController",
                    "control_policy": "FIFO",
                    "process_ids": ["TP1"],
                    "state_ids": ["Breakdownstate_1"],
                },
            ]
        }
    )
