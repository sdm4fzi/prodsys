from __future__ import annotations

from enum import Enum
from pydantic import BaseModel
from typing import Literal, Union, Optional, List, Tuple, TYPE_CHECKING

from prodsim.data_structures.performance_indicators import KPIEnum, KPILevelEnum, KPI_UNION

if TYPE_CHECKING:
    from prodsim.simulation import state

class Event(BaseModel):
    time: float
    resource: str
    state: str
    # state_type: state.StateTypeEnum
    state_type: str
    # activity: state.StateEnum
    activity: str
    material: Optional[str] = None
    expected_end_time: Optional[float] = None
    target_location: Optional[str] = None

class Performance(BaseModel):
    event_log: List[Event]
    kpis: List[KPI_UNION]

    def get_kpi_for_context(self, context: Tuple[KPILevelEnum, ...]) -> List[KPI_UNION]:
        return [kpi for kpi in self.kpis if context == kpi.context]
    
    def get_kpi_for_name(self, name: KPIEnum) -> List[KPI_UNION]:
        return [kpi for kpi in self.kpis if name == kpi.name]
    
    def get_kpi_for_context_and_name(self, context: Tuple[KPILevelEnum, ...], name: KPIEnum) -> List[KPI_UNION]:
        return [kpi for kpi in self.kpis if context == kpi.context and name == kpi.name]
    


