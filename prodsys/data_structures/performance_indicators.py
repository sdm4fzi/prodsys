from __future__ import annotations

from enum import Enum
from typing import Literal, List, Optional, Union, Tuple

from pydantic import BaseModel, validator


class KPIEnum(str, Enum):
    """
    Enum that represents the different kind of KPIs.
    """

    OUTPUT = "output"
    THROUGHPUT = "throughput"
    COST = "cost"
    WIP = "WIP"

    TRHOUGHPUT_TIME = "throughput_time"
    PROCESSING_TIME = "processing_time"

    PRODUCTIVE_TIME = "productive_time"
    STANDBY_TIME = "standby_time"
    SETUP_TIME = "setup_time"
    UNSCHEDULED_DOWNTIME = "unscheduled_downtime"

    DYNAMIC_WIP = "dynamic_WIP"
    DYNAMIC_THROUGHPUT_TIME = "dynamic_throughput_time"


class KPILevelEnum(str, Enum):
    """
    Enum that represents the different kind of KPI levels.
    """

    SYSTEM = "system"
    RESOURCE = "resource"
    ALL_MATERIALS = "all_materials"
    MATERIAL_TYPE = "material_type"
    MATERIAL = "material"
    PROCESS = "process"


class KPI(BaseModel):
    """
    Class that represents a KPI. Not intended for usage but only inheritance.

    Args:
        name (KPIEnum): Name of the KPI.
        target (Literal["min", "max"]): Favourable target of the KPI.
        weight (Optional[float], optional): Weight of the KPI. Defaults to 1.
        value (Optional[float], optional): Value of the KPI. Defaults to None.
        context (Tuple[KPILevelEnum, ...], optional): Context of the KPI. Defaults to None.
        resource (Optional[str], optional): Resource of the KPI. Defaults to None.
        material_type (Optional[str], optional): Material type of the KPI. Defaults to None.    Returns:
    """

    name: KPIEnum
    target: Literal["min", "max"]
    weight: Optional[float] = 1
    value: Optional[float] = None
    context: Tuple[KPILevelEnum, ...] = None
    resource: Optional[str] = None
    material_type: Optional[str] = None

    @validator("context")
    def sort_context(cls, v):
        return tuple(sorted(v))


class DynamicKPI(KPI):
    """
    Class that represents a dynamic KPI. Not intended for usage but only inheritance.
    """

    start_time: float
    end_time: float
    material: Optional[str] = None
    process: Optional[str] = None


class Output(KPI):
    name: Literal[KPIEnum.OUTPUT] = KPIEnum.OUTPUT
    target: Literal["max"] = "max"

    class Config:
        schema_extra = {
            "example": {
                "summary": "Output KPI",
                "value": {
                    "name": "output",
                    "target": "max",
                    "weight": 1,
                    "value": 34,
                    "context": ["system", "material_type"],
                    "material_type": "MaterialType_1",
                },
            }
        }


class Throughput(KPI):
    name: Literal[KPIEnum.THROUGHPUT]
    target: Literal["max"] = "max"

    class Config:
        schema_extra = {
            "example": {
                "summary": "Throughput KPI",
                "value": {
                    "name": "throughput",
                    "target": "max",
                    "weight": 1,
                    "value": 4.32,
                    "context": ["system", "material_type"],
                    "material_type": "MaterialType_1",
                },
            }
        }


class Cost(KPI):
    name: Literal[KPIEnum.COST]
    target: Literal["min"] = "min"

    class Config:
        schema_extra = {
            "example": {
                "summary": "Cost KPI",
                "value": {
                    "name": "cost",
                    "target": "min",
                    "weight": 0.5,
                    "value": 36000,
                    "context": ["system"],
                },
            }
        }


class WIP(KPI):
    name: Literal[KPIEnum.WIP]
    target: Literal["min"] = "min"

    class Config:
        schema_extra = {
            "example": {
                "summary": "WIP KPI",
                "value": {
                    "name": "WIP",
                    "target": "min",
                    "weight": 1,
                    "value": 121,
                    "context": ["system", "material_type"],
                    "material_type": "MaterialType_1",
                },
            }
        }


class DynamicWIP(DynamicKPI, WIP):
    name: Literal[KPIEnum.DYNAMIC_WIP]
    target: Literal["min"] = "min"

    class Config:
        schema_extra = {
            "example": {
                "summary": "Dynamic WIP KPI",
                "value": {
                    "name": "dynamic_WIP",
                    "target": "min",
                    "weight": 1,
                    "value": 121,
                    "context": ["system", "material"],
                    "material_type": "MaterialType_1",
                    "start_time": 21.2,
                    "end_time": 23.4,
                },
            }
        }


class ThroughputTime(KPI):
    name: Literal[KPIEnum.TRHOUGHPUT_TIME]
    target: Literal["min"] = "min"

    class Config:
        schema_extra = {
            "example": {
                "summary": "Throughput time KPI",
                "value": {
                    "name": "throughput_time",
                    "target": "min",
                    "weight": 1,
                    "value": 221.1,
                    "context": ["system", "material_type"],
                    "material_type": "MaterialType_1",
                },
            }
        }


class DynamicThroughputTime(DynamicKPI, ThroughputTime):
    name: Literal[KPIEnum.DYNAMIC_THROUGHPUT_TIME]
    target: Literal["min"] = "min"

    class Config:
        schema_extra = {
            "example": {
                "summary": "Dynamic throughput time KPI",
                "value": {
                    "name": "throughput_time",
                    "target": "min",
                    "weight": 1,
                    "value": 201.3,
                    "context": ["system", "material"],
                    "material_type": "MaterialType_1",
                    "material": "Material_1_23",
                },
            }
        }


class ProcessingTime(KPI):
    name: Literal[KPIEnum.PROCESSING_TIME]
    target: Literal["min"] = "min"

    class Config:
        schema_extra = {
            "example": {
                "summary": "Processing time KPI",
                "value": {
                    "name": "processing_time",
                    "target": "min",
                    "weight": 1,
                    "value": 1.2,
                    "context": ["resource", "process"],
                    "resource": "Resource_1",
                    "process": "P1",
                },
            }
        }


class ProductiveTime(KPI):
    name: Literal[KPIEnum.PRODUCTIVE_TIME]
    target: Literal["max"] = "max"

    class Config:
        schema_extra = {
            "example": {
                "summary": "Productive time KPI",
                "value": {
                    "name": "productive_time",
                    "target": "max",
                    "weight": 1,
                    "value": 0.65,
                    "context": ["resource"],
                    "resource": "Resource_1",
                },
            }
        }


class StandbyTime(KPI):
    name: Literal[KPIEnum.STANDBY_TIME]
    target: Literal["min"] = "min"

    class Config:
        schema_extra = {
            "example": {
                "summary": "Standby time KPI",
                "value": {
                    "name": "standby_time",
                    "target": "min",
                    "weight": 1,
                    "value": 0.12,
                    "context": ["resource"],
                    "resource": "Resource_1",
                },
            }
        }


class SetupTime(KPI):
    name: Literal[KPIEnum.SETUP_TIME]
    target: Literal["min"] = "min"

    class Config:
        schema_extra = {
            "example": {
                "summary": "Setup time KPI",
                "value": {
                    "name": "setup_time",
                    "target": "min",
                    "weight": 1,
                    "value": 0.08,
                    "context": ["resource"],
                    "resource": "Resource_1",
                },
            }
        }


class UnscheduledDowntime(KPI):
    name: Literal[KPIEnum.UNSCHEDULED_DOWNTIME]
    target: Literal["min"] = "min"

    class Config:
        schema_extra = {
            "example": {
                "summary": "Unscheduled downtime KPI",
                "value": {
                    "name": "unscheduled_downtime",
                    "target": "min",
                    "weight": 1,
                    "value": 0.1,
                    "context": ["resource"],
                    "resource": "Resource_1",
                },
            }
        }


KPI_UNION = Union[
    Output,
    Throughput,
    Cost,
    WIP,
    ThroughputTime,
    ProcessingTime,
    ProductiveTime,
    StandbyTime,
    SetupTime,
    UnscheduledDowntime,
    DynamicWIP,
    DynamicThroughputTime,
]
