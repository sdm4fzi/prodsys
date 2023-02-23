from __future__ import annotations

from typing import Literal, Union, List, Tuple, Optional

from pydantic import validator

from prodsim.data_structures.core_asset import CoreAsset


class ResourceData(CoreAsset):
    capacity: int
    location: Tuple[float, float]

    controller: Literal["SimpleController", "TransportController"]
    control_policy: Literal["FIFO", "SPT_transport", "LIFO", "SPT"]

    processes: List[str]
    process_capacity: Optional[List[int]]
    states: Optional[List[str]] = []

    @validator("process_capacity")
    def check_process_capacity(cls, v, values):
        if not v:
            return None

        if len(v) != len(values["processes"]):
            raise ValueError("process_capacity must have the same length as processes")
        if max(v) > values["capacity"]:
            raise ValueError("process_capacity must be smaller than capacity")
        return v

    class Config:
        schema_extra = {
            "example": {
                "ID": "R1",
                "description": "Resource 1",
                "capacity": 2,
                "location": [10.0, 10.0],
                "controller": "SimpleController",
                "control_policy": "FIFO",
                "processes": ["P1", "P2"],
                "process_capacity": [2, 1],
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
    controller: Literal["SimpleController"]
    control_policy: Literal["FIFO", "LIFO", "SPT"]

    input_queues: Optional[List[str]]
    output_queues: Optional[List[str]]


class TransportResourceData(ResourceData):

    controller: Literal["TransportController"]
    control_policy: Literal["FIFO", "SPT_transport"]

    class Config:
        schema_extra = {
            "example": {
                "ID": "TR1",
                "description": "Transport Resource 1",
                "capacity": 1,
                "location": [15.0, 15.0],
                "controller": "TransportController",
                "control_policy": "FIFO",
                "processes": ["TP1"],
                "process_capacity": None,
                "states": ["Breakdownstate_1"],
            }
        }


RESOURCE_DATA_UNION = Union[ProductionResourceData, TransportResourceData]
