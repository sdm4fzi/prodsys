from __future__ import annotations

from enum import Enum
from typing import Literal

from .core_asset import CoreAsset

class ProcessTypeEnum(str, Enum):
    ProductionProcesses = "ProductionProcesses"
    TransportProcesses = "TransportProcesses"

class ProcessData(CoreAsset):
    time_model_id: str
    # type: Literal[ProcessTypeEnum.ProductionProcesses, ProcessTypeEnum.TransportProcesses]

class ProductionProcessData(ProcessData):
    type: Literal[ProcessTypeEnum.ProductionProcesses]

class TransportProcessData(ProcessData):
    type: Literal[ProcessTypeEnum.TransportProcesses]
