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


class ProductionResourceData(ResourceData):
    # type: Literal[ResourceType.ProductionResource]

    controller: Literal["SimpleController"]
    control_policy: Literal["FIFO", "LIFO", "SPT"]

    input_queues: Optional[List[str]]
    output_queues: Optional[List[str]]


class TransportResourceData(ResourceData):

    controller: Literal["TransportController"]
    control_policy: Literal["FIFO", "SPT_transport"]


RESOURCE_DATA_UNION = Union[ProductionResourceData, TransportResourceData]
