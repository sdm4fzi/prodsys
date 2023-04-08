from __future__ import annotations

from enum import Enum
from typing import Literal, Union, Optional

from prodsim.data_structures.core_asset import CoreAsset


class ProcessTypeEnum(str, Enum):
    ProductionProcesses = "ProductionProcesses"
    TransportProcesses = "TransportProcesses"
    CapabilityProcesses = "CapabilityProcesses"


class ProcessData(CoreAsset):
    time_model_id: str

    class Config:
        schema_extra = {
            "example": {
                "ID": "P1",
                "description": "Process 1",
                "time_model_id": "function_time_model_1",
            }
        }


class ProductionProcessData(ProcessData):
    type: Literal[ProcessTypeEnum.ProductionProcesses]

    class Config:
        schema_extra = {
            "example": {
                "ID": "P1",
                "description": "Process 1",
                "time_model_id": "function_time_model_1",
                "type": "ProductionProcesses",
            }
        }


class CapabilityProcessData(ProcessData):
    type: Literal[ProcessTypeEnum.CapabilityProcesses]
    capability: str

    class Config:
        schema_extra = {
            "example": {
                "ID": "P1",
                "description": "Process 1",
                "time_model_id": "function_time_model_1",
                "type": "ProductionProcesses",
                "capability": "C1",
            }
        }


class TransportProcessData(ProcessData):
    type: Literal[ProcessTypeEnum.TransportProcesses]

    class Config:
        schema_extra = {
            "example": {
                "ID": "TP1",
                "description": "Transport Process 1",
                "time_model_id": "manhattan_time_model_1",
                "type": "TransportProcesses",
            }
        }


PROCESS_DATA_UNION = Union[
    ProductionProcessData, TransportProcessData, CapabilityProcessData
]
