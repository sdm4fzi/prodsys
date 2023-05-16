from __future__ import annotations

from typing import Union

from prodsys.data_structures.core_asset import CoreAsset
from pydantic import validator


class QueueData(CoreAsset):
    capacity: Union[int, float] = 0.0

    class Config:
        schema_extra = {
            "example": {
                "ID": "Q1",
                "description": "Queue 1",
                "capacity": 10,
            }
        }
