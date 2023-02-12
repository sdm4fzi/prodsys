from __future__ import annotations

from enum import Enum
from typing import Literal, List, Optional, Dict, Tuple, Union

from pydantic import BaseModel, validator

class KPIEnum(str, Enum):
    THROUGHPUT = "throughput"
    COST = "cost"
    WIP = "WIP"
    TRHOUGHPUT_TIME = "throughput_time"

class KPI(BaseModel):
    name: KPIEnum
    target: Literal["min", "max"]
    weight: Optional[float] = 1


class ThroughputKPI(KPI):
    name: Literal["throughput"]
    target: Literal["max"] = "max"

class CostKPI(KPI):
    name: Literal["cost"]
    target: Literal["min"] = "min"

class WIPKPI(KPI):
    name: Literal["WIP"]
    target: Literal["min"] = "min"

class ThroughputTimeKPI(KPI):
    name: Literal["throughput_time"]
    target: Literal["min"] = "min"

KPI_UNION = Union[ThroughputKPI, CostKPI, WIPKPI, ThroughputTimeKPI]

class ScenarioConstrainsData(BaseModel):
    max_reconfiguration_cost: float
    max_num_machines: int
    max_num_processes_per_machine: int
    max_num_transport_resources: int
    target_material_count: Optional[Dict[str, int]]

class ScenarioOptionsData(BaseModel):
    machine_controllers: List[Literal["FIFO", "LIFO", "SPT"]]
    transport_controllers: List[Literal["FIFO", "SPT_transport"]]
    positions: List[Tuple[float, float]]

    @validator("positions")
    def check_positions(cls, v):
        new_v = []
        for e in v:
            if len(e) != 2:
                raise ValueError("positions must be a list of tuples of length 2")
            new_v.append(tuple(e))

        return new_v

class ScenarioInfoData(BaseModel):
    machine_cost: float
    transport_resource_cost: float
    process_module_cost: float
    breakdown_cost: Optional[float]
    time_range: Optional[int]
    maximum_breakdown_time: Optional[int]

class ScenarioData(BaseModel):
    constraints: ScenarioConstrainsData
    options: ScenarioOptionsData
    info: ScenarioInfoData
    optimize: List[KPIEnum]
    weights: Optional[Dict[KPIEnum, float]]

    @validator("weights")
    def check_weights(cls, v, values):
        if v is None:
            print("v is none")
            return v
        for kpi in values["optimize"]:
            if kpi not in v:
                raise ValueError(f"Weight for {kpi} not specified")
        return v