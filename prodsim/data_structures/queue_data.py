from __future__ import annotations

from typing import Union

from .core_asset import CoreAsset
from pydantic import validator

class QueueData(CoreAsset):
    capacity: Union[int, float] = float("inf")

    # @validator("capacity", always=True)
    # def check_output_queue(cls, v, values):
    #     if not v or values["ID"] == "SinkQueue" or values["ID"] == "SourceQueue":
    #         return float('inf')
    #     if v < 1:
    #         raise ValueError("Capacity must be greater than 0")
    #     return v

