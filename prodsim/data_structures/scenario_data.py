from __future__ import annotations

from typing import Literal, List, Optional, Dict
from enum import Enum

from pydantic import BaseModel, validator, conlist

from prodsim.data_structures.performance_indicators import KPIEnum

class ReconfigurationEnum(str, Enum):
    PRODUCTION_CAPACITY = "production_capacity"
    TRANSPORT_CAPACITY = "transport_capacity"
    LAYOUT = "layout"
    SEQUENCING_LOGIC = "sequencing_logic"
    ROUTING_LOGIC = "routing_logic"

class ScenarioConstrainsData(BaseModel):
    max_reconfiguration_cost: float
    max_num_machines: int
    max_num_processes_per_machine: int
    max_num_transport_resources: int
    target_material_count: Optional[Dict[str, int]]

    class Config:
        schema_extra = {
            "example": {
                "max_reconfiguration_cost": 120000,
                "max_num_machines": 10,
                "max_num_processes_per_machine": 2,
                "max_num_transport_resources": 2,
                "target_material_count": {"Material_1": 120, "Material_2": 200},
            }
        }

class ScenarioOptionsData(BaseModel):
    transformations: List[ReconfigurationEnum]
    machine_controllers: List[Literal["FIFO", "LIFO", "SPT"]]
    transport_controllers: List[Literal["FIFO", "SPT_transport"]]
    routing_heuristics: List[Literal["shortest_queue", "random", "FIFO"]]
    positions: List[conlist(float, min_items=2, max_items=2)]

    @validator("positions")
    def check_positions(cls, v):
        for e in v:
            if len(e) != 2:
                raise ValueError("positions must be a list of tuples of length 2")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "machine_controllers": ["FIFO", "LIFO", "SPT"],
                "transport_controllers": ["FIFO", "SPT_transport"],
                "positions": [[10.0, 10.0], [20.0, 20.0]],
            }
        }

class ScenarioInfoData(BaseModel):
    machine_cost: float
    transport_resource_cost: float
    process_module_cost: float
    breakdown_cost: Optional[float]
    time_range: Optional[int]
    maximum_breakdown_time: Optional[int]

    class Config:
        schema_extra = {
            "example": {
                "machine_cost": 30000,
                "transport_resource_cost": 20000,
                "process_module_cost": 2300,
                "breakdown_cost": 1000,
                "time_range": 2600,
                "maximum_breakdown_time": 10,
            }
        }

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