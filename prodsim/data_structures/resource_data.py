from __future__ import annotations

from typing import Literal, Union, List, Tuple, Optional
from enum import Enum

from pydantic import validator, conlist

from prodsim.data_structures.core_asset import CoreAsset

class ControllerEnum(str, Enum):
    PipelineController = "PipelineController"
    TransportController = "TransportController"

class ResourceControlPolicy(str, Enum):
    FIFO = "FIFO"
    LIFO = "LIFO"
    SPT = "SPT"

class TransportControlPolicy(str, Enum):
    FIFO = "FIFO"
    SPT_transport = "SPT_transport"

class ResourceData(CoreAsset):
    capacity: int
    location: conlist(float, min_items=2, max_items=2)

    controller: ControllerEnum
    control_policy: Union[ResourceControlPolicy, TransportControlPolicy]

    process_ids: List[str]
    process_capacities: Optional[List[int]]
    state_ids: Optional[List[str]] = []

    @validator("process_capacities")
    def check_process_capacity(cls, v, values):
        if not v:
            return None

        if len(v) != len(values["process_ids"]) and sum(v) != len(values["process_ids"]):
            raise ValueError(f"process_capacities {v} must have the same length as processes {values['process_ids']}")
        if max(v) > values["capacity"]:
            raise ValueError("process_capacities must be smaller than capacity")
        return v

    class Config:
        schema_extra = {
            "example": {
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
            }
        }


class ProductionResourceData(ResourceData):
    controller: Literal[ControllerEnum.PipelineController]
    control_policy: ResourceControlPolicy

    input_queues: Optional[List[str]]
    output_queues: Optional[List[str]]


class TransportResourceData(ResourceData):

    controller: Literal[ControllerEnum.TransportController]
    control_policy: TransportControlPolicy

    class Config:
        schema_extra = {
            "example": {
                "ID": "TR1",
                "description": "Transport Resource 1",
                "capacity": 1,
                "location": [15.0, 15.0],
                "controller": "TransportController",
                "control_policy": "FIFO",
                "process_ids": ["TP1"],
                "process_capacities": None,
                "states": ["Breakdownstate_1"],
            }
        }


RESOURCE_DATA_UNION = Union[ProductionResourceData, TransportResourceData]
