from __future__ import annotations

from enum import Enum
from typing import Literal

from .core_asset import CoreAsset

class ProcessTypeEnum(str, Enum):
    ProductionProcesses = "ProductionProcesses"
    TransportProcesses = "TransportProcess"

