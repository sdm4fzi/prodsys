from __future__ import annotations

from enum import Enum
from typing import Literal, List, Optional, Union, Tuple

from pydantic import BaseModel, validator


class KPIEnum(str, Enum):
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
    SYSTEM = "system"
    RESOURCE = "resource"
    ALL_MATERIALS = "all_materials"
    MATERIAL_TYPE = "material_type"
    MATERIAL = "material"
    PROCESS = "process"


class KPI(BaseModel):
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
    start_time: float
    end_time: float
    material: Optional[str] = None
    process: Optional[str] = None


class Output(KPI):
    name: Literal[KPIEnum.OUTPUT]
    target: Literal["max"] = "max"


class Throughput(KPI):
    name: Literal[KPIEnum.THROUGHPUT]
    target: Literal["max"] = "max"


class Cost(KPI):
    name: Literal[KPIEnum.COST]
    target: Literal["min"] = "min"


class WIP(KPI):
    name: Literal[KPIEnum.WIP]
    target: Literal["min"] = "min"


class DynamicWIP(DynamicKPI, WIP):
    name: Literal[KPIEnum.DYNAMIC_WIP]


class ThroughputTime(KPI):
    name: Literal[KPIEnum.TRHOUGHPUT_TIME]
    target: Literal["min"] = "min"

class DynamicThroughputTime(DynamicKPI, ThroughputTime):
    name: Literal[KPIEnum.DYNAMIC_THROUGHPUT_TIME]


class ProcessingTime(KPI):
    name: Literal[KPIEnum.PROCESSING_TIME]
    target: Literal["min"] = "min"

class ProductiveTime(KPI):
    name: Literal[KPIEnum.PRODUCTIVE_TIME]
    target: Literal["max"] = "max"


class StandbyTime(KPI):
    name: Literal[KPIEnum.STANDBY_TIME]
    target: Literal["min"] = "min"


class SetupTime(KPI):
    name: Literal[KPIEnum.SETUP_TIME]
    target: Literal["min"] = "min"


class UnscheduledDowntime(KPI):
    name: Literal[KPIEnum.UNSCHEDULED_DOWNTIME]
    target: Literal["min"] = "min"


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
