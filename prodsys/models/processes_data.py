"""
The `processes_data` module contains the `prodsys.models` classes to represent the processes that can 
be performed on products by resources.

The following processes are possible:
- `ProductionProcessData`: A process that can be performed on a product by a production resource.
- `CapabilityProcessData`: A process that can be performed on a product by a resource, based on the capability of the resource.
- `TransportProcessData`: A process that can be performed on a product by a transport resource.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Union, Optional

from prodsys.models.core_asset import CoreAsset


class ProcessTypeEnum(str, Enum):
    """
    Enum that represents the different kind of processes.
    """

    ProductionProcesses = "ProductionProcesses"
    TransportProcesses = "TransportProcesses"
    CapabilityProcesses = "CapabilityProcesses"


class ProcessData(CoreAsset):
    """
    Class that represents process data. Acts as a base class for all process data classes.

    Args:
        ID (str): ID of the process.
        description (str): Description of the process.
        time_model_id (str): ID of the time model of the process.
    """

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
    """
    Class that represents production process data.

    Args:
        ID (str): ID of the process.
        description (str): Description of the process.
        time_model_id (str): ID of the time model of the process.
        type (Literal[ProcessTypeEnum.ProductionProcesses]): Type of the process.

    Examples:
        A production process with ID "P1", description "Process 1" and time model ID "function_time_model_1":
        ``` py
        import prodsys
        prodsys.processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="function_time_model_1",
            type="ProductionProcesses",
        )
        ```
    """

    type: Literal[ProcessTypeEnum.ProductionProcesses]

    class Config:
        schema_extra = {
            "example": {
                "summary": "Production process",
                "value": {
                    "ID": "P1",
                    "description": "Process 1",
                    "time_model_id": "function_time_model_1",
                    "type": "ProductionProcesses",
                },
            }
        }


class CapabilityProcessData(ProcessData):
    """
    Class that represents capability process data. Capability processes are not compared by their IDs but their Capabilities.

    Args:
        ID (str): ID of the process.
        description (str): Description of the process.
        time_model_id (str): ID of the time model of the process.
        type (Literal[ProcessTypeEnum.CapabilityProcesses]): Type of the process.
        capability (str): Capability of the process.

    Examples:
        A capability process with ID "P1", description "Process 1", time model ID "function_time_model_1" and capability "C1":
        ``` py
        import prodsys
        prodsys.processes_data.CapabilityProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="function_time_model_1",
            type="CapabilityProcesses",
            capability="C1",
        )
        ```
    """

    type: Literal[ProcessTypeEnum.CapabilityProcesses]
    capability: str

    class Config:
        schema_extra = {
            "example": {
                "summary": "Capability process",
                "value": {
                    "ID": "P1",
                    "description": "Process 1",
                    "time_model_id": "function_time_model_1",
                    "type": "CapabilityProcesses",
                    "capability": "C1",
                },
            }
        }


class TransportProcessData(ProcessData):
    """
    Class that represents transport process data.

    Args:
        ID (str): ID of the process.
        description (str): Description of the process.
        time_model_id (str): ID of the time model of the process
        type (Literal[ProcessTypeEnum.TransportProcesses]): Type of the process.

    Examples:
        A transport process with ID "TP1", description "Transport Process 1" and time model ID "manhattan_time_model_1":
        ``` py
        import prodsys
        prodsys.processes_data.TransportProcessData(
            ID="TP1",
            description="Transport Process 1",
            time_model_id="manhattan_time_model_1",
            type="TransportProcesses",
        )
        ```
    """

    type: Literal[ProcessTypeEnum.TransportProcesses]

    class Config:
        schema_extra = {
            "example": {
                "summary": "Transport process",
                "value": {
                    "ID": "TP1",
                    "description": "Transport Process 1",
                    "time_model_id": "manhattan_time_model_1",
                    "type": "TransportProcesses",
                },
            }
        }


PROCESS_DATA_UNION = Union[
    ProductionProcessData, TransportProcessData, CapabilityProcessData
]
