from __future__ import annotations

from enum import Enum
from pydantic import BaseModel
from typing import Literal, Union, Optional, List, Tuple, TYPE_CHECKING

from prodsys.models.performance_indicators import (
    KPIEnum,
    KPILevelEnum,
    KPI_UNION,
)

if TYPE_CHECKING:
    from prodsys.simulation import state


class Event(BaseModel):
    """
    Class that represents an event in the event log.

    Args:
        time (float): Time of the event.
        resource (str): Resource of the event.
        state (str): State of the event.
        state_type (str): State type of the event, representing a state.StateTypeEnum.
        activity (str): Activity of the event, representing a state.StateEnum.
        product (Optional[str], optional): Product of the event. Defaults to None.
        expected_end_time (Optional[float], optional): Expected end time of the event. Defaults to None.
        target_location (Optional[str], optional): Target location of the event. Defaults to None.
    """

    time: float
    resource: str
    state: str
    state_type: str
    activity: str
    product: Optional[str] = None
    expected_end_time: Optional[float] = None
    target_location: Optional[str] = None

    class Config:
        schema_extra = {
            "examples": [
                {
                    "time": 12.0,
                    "resource": "R1",
                    "state": "P1",
                    "state_type": "Production",
                    "activity": "start state",
                    "product": "Product_1_12",
                    "expected_end_time": 24.3,
                    "target_location": None,
                },
                {
                    "time": 24.3,
                    "resource": "R1",
                    "state": "P1",
                    "state_type": "Production",
                    "activity": "end state",
                    "product": "Product_1_12",
                    "expected_end_time": None,
                    "target_location": None,
                },
            ]
        }


class Performance(BaseModel):
    """
    Class that represents the performance of a simulation run.

    Args:
        event_log (List[Event]): Event log of the simulation run.
        kpis (List[KPI_UNION]): List of KPIs of the simulation run.
    """

    event_log: List[Event]
    kpis: List[KPI_UNION]

    def get_kpi_for_context(self, context: Tuple[KPILevelEnum, ...]) -> List[KPI_UNION]:
        return [kpi for kpi in self.kpis if context == kpi.context]

    def get_kpi_for_name(self, name: KPIEnum) -> List[KPI_UNION]:
        return [kpi for kpi in self.kpis if name == kpi.name]

    def get_kpi_for_context_and_name(
        self, context: Tuple[KPILevelEnum, ...], name: KPIEnum
    ) -> List[KPI_UNION]:
        return [kpi for kpi in self.kpis if context == kpi.context and name == kpi.name]
