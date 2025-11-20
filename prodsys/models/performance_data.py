from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Tuple

from prodsys.models.performance_indicators import (
    KPIEnum,
    KPILevelEnum,
    KPI_UNION,
)


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
        origin_location (Optional[str], optional): Origin location of the event. Defaults to None.
        target_location (Optional[str], optional): Target location of the event. Defaults to None.
        empty_transport (Optional[bool], optional): Whether the transport is empty. Defaults to None.
        requesting_item (Optional[str], optional): ID of the item requesting a dependency. Defaults to None.
        dependency (Optional[str], optional): ID of the dependency. Defaults to None.
    """

    time: float = Field(alias="Time")
    resource: str = Field(alias="Resource")
    state: Optional[str] = Field(default=None, alias="State")
    state_type: str = Field(alias="State Type")
    activity: str = Field(alias="Activity")
    product: Optional[str] = Field(default=None, alias="Product")
    expected_end_time: Optional[float] = Field(default=None, alias="Expected End Time")
    origin_location: Optional[str] = Field(default=None, alias="Origin location")
    target_location: Optional[str] = Field(default=None, alias="Target location")
    empty_transport: Optional[bool] = Field(default=None, alias="Empty Transport")
    requesting_item: Optional[str] = Field(default=None, alias="Requesting Item")
    dependency: Optional[str] = Field(default=None, alias="Dependency")
    process: Optional[str] = Field(default=None, alias="process")

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
        json_schema_extra={
            "examples": [
                {
                    "Time": 12.0,
                    "Resource": "R1",
                    "State": "P1",
                    "State Type": "Production",
                    "Activity": "start state",
                    "Product": "Product_1_12",
                    "Expected End Time": 24.3,
                    "Origin location": "",
                    "Target location": "",
                    "Empty Transport": None,
                    "Requesting Item": None,
                    "Dependency": None,
                },
                {
                    "Time": 24.3,
                    "Resource": "R1",
                    "State": "P1",
                    "State Type": "Production",
                    "Activity": "end state",
                    "Product": "Product_1_12",
                    "Expected End Time": None,
                    "Origin location": "",
                    "Target location": "L1",
                    "Empty Transport": None,
                    "Requesting Item": None,
                    "Dependency": None,
                },
            ]
        }
    )


class Performance(BaseModel):
    """
    Class that represents the performance of a simulation run.

    Args:
        event_log (List[Event]): Event log of the simulation run.
        kpis (List[KPI_UNION]): List of KPIs of the simulation run.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "event_log": Event.model_config["json_schema_extra"]["examples"],
                    "kpis": [
                        {
                            "name": "throughput",
                            "target": "max",
                            "weight": 1,
                            "value": 4.32,
                            "context": ["system", "product_type"],
                            "product_type": "ProductType_1",
                        },
                        {
                            "name": "WIP",
                            "target": "min",
                            "weight": 1,
                            "value": 121,
                            "context": ["system", "product_type"],
                            "product_type": "ProductType_1",
                        },
                    ],
                }
            ]
        }
    )

    event_log: Optional[List[Event]]
    kpis: List[KPI_UNION]

    def get_kpi_for_context(self, context: Tuple[KPILevelEnum, ...]) -> List[KPI_UNION]:
        return [kpi for kpi in self.kpis if context == kpi.context]

    def get_kpi_for_name(self, name: KPIEnum) -> List[KPI_UNION]:
        return [kpi for kpi in self.kpis if name == kpi.name]

    def get_kpi_for_context_and_name(
        self, context: Tuple[KPILevelEnum, ...], name: KPIEnum
    ) -> List[KPI_UNION]:
        return [kpi for kpi in self.kpis if context == kpi.context and name == kpi.name]
