from __future__ import annotations

from typing import Union

from prodsim.data_structures.core_asset import CoreAsset
from pydantic import validator


class QueueData(CoreAsset):
    capacity: Union[int, float] = float("inf")
