"""
In `prodsys` exist two different types of resources: production resources and transport resources. Production resources are resources that can perform processes on products. Transport resources are resources that can transport products from one location to another. Both types of resources are represented by the `ResourceData` class. The `ResourceData` class is an abstract base class and cannot be instantiated. Instead, the `ProductionResourceData` and `TransportResourceData` classes can be used to represent production resources and transport resources, respectively.

The following resources are available:

- `ProductionResourceData`: Class that represents a production resource.
- `TransportResourceData`: Class that represents a transport resource.
"""

from __future__ import annotations

from typing import Literal, Union, List, Tuple, Optional
from enum import Enum

from pydantic import validator, conlist

from prodsys.data_structures.core_asset import CoreAsset


class ControllerEnum(str, Enum):
    """
    Enum that represents the controller of a resource.
    """

    PipelineController = "PipelineController"
    TransportController = "TransportController"


class ResourceControlPolicy(str, Enum):
    """
    Enum that represents the control policy of a resource.
    """

    FIFO = "FIFO"
    LIFO = "LIFO"
    SPT = "SPT"


class TransportControlPolicy(str, Enum):
    """
    Enum that represents the control policy of a transport resource.
    """

    FIFO = "FIFO"
    SPT_transport = "SPT_transport"


class ResourceData(CoreAsset):
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
    location: conlist(float, min_items=2, max_items=2)

    controller: ControllerEnum
    control_policy: Union[ResourceControlPolicy, TransportControlPolicy]

    process_ids: List[str]
    process_capacities: Optional[List[int]]
    state_ids: Optional[List[str]] = []

    @validator("process_capacities", always=True)
    def check_process_capacity(cls, v, values):
        if not v:
            return [values["capacity"] for _ in values["process_ids"]]
        if len(v) != len(values["process_ids"]):
            raise ValueError(
                f"process_capacities {v} must have the same length as processes {values['process_ids']}"
            )
        if max(v) > values["capacity"]:
            raise ValueError("process_capacities must be smaller than capacity")
        return v


class ProductionResourceData(ResourceData):
    """
    Class that represents production resource data.

    Args:
        ID (str): ID of the resource.
        description (str): Description of the resource.
        capacity (int): Capacity of the resource.
        location (List[float]): Location of the resource. Has to be a list of length 2.
        controller (Literal[ControllerEnum.PipelineController]): Controller of the resource, has to be a PipelineController.
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

    controller: Literal[ControllerEnum.PipelineController]
    control_policy: ResourceControlPolicy

    input_queues: Optional[List[str]]
    output_queues: Optional[List[str]]

    class Config:
        schema_extra = {
            "example": {
                "summary": "Production Resource Data",
                "value": {
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
                        "Setup_State_2",
                        "ProcessBreakdownState_1",
                    ],
                    "input_queues": ["IQ1"],
                    "output_queues": ["OQ1"],
                },
            }
        }


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

    class Config:
        schema_extra = {
            "example": {
                "summary": "Transport Resource Data",
                "value": {
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
            }
        }


RESOURCE_DATA_UNION = Union[ProductionResourceData, TransportResourceData]
