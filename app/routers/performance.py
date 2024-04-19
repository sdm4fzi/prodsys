from typing import List


from fastapi import APIRouter, HTTPException


from prodsys.models import (
    performance_data,
    performance_indicators
)
from app.dependencies import prodsys_backend

KPI_EXAMPLES = {
    "Output": performance_indicators.Output.Config.schema_extra["example"],
    "Throughput": performance_indicators.Throughput.Config.schema_extra["example"],
    "Cost" : performance_indicators.Cost.Config.schema_extra["example"],
    "WIP": performance_indicators.WIP.Config.schema_extra["example"],
    "ThroughputTime": performance_indicators.ThroughputTime.Config.schema_extra["example"],
    "ProcessingTime": performance_indicators.ProcessingTime.Config.schema_extra["example"],
    "ProductiveTime": performance_indicators.ProductiveTime.Config.schema_extra["example"],
    "StandbyTime": performance_indicators.StandbyTime.Config.schema_extra["example"],
    "SetupTime": performance_indicators.SetupTime.Config.schema_extra["example"],
    "UnscheduledDowntime": performance_indicators.UnscheduledDowntime.Config.schema_extra["example"],
    "DynamicWIP": performance_indicators.DynamicWIP.Config.schema_extra["example"],
    "DynamicThroughputTime": performance_indicators.DynamicThroughputTime.Config.schema_extra["example"],
}    

KPI_LIST_EXAMPLE = [item["value"] for item in KPI_EXAMPLES.values()]


router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/performance",
    tags=["performance"],
    responses={404: {"description": "Not found"}},
)

@router.get(
    "/kpis",
    response_model=List[performance_indicators.KPI_UNION],
    responses={
        200: {
            "description": "Sucessfully returned static results",
            "content": {
                "application/json": {
                    "example": KPI_LIST_EXAMPLE
                }
            }
        },
        404: {"description": "No KPIs found"},
    }
)
async def get_kpis(project_id: str, adapter_id: str):
    performance = prodsys_backend.get_performance(project_id, adapter_id)
    return performance.kpis


@router.get(
    "/kpis/{kpi}",
    response_model=List[performance_indicators.KPI_UNION],
    responses={
        200: {
            "description": "Sucessfully returned static results",
            "content": {
                "application/json": {
                    "examples": KPI_EXAMPLES
                }
            }
        },
        404: {"description": "No KPIs found"},
    }
)
async def get_kpi(
    project_id: str, adapter_id: str, kpi: performance_indicators.KPIEnum
):
    enum_values = tuple(item for item in performance_indicators.KPIEnum)
    if kpi not in enum_values:
        raise HTTPException(404, f"KPI {kpi} not found")
    performance = prodsys_backend.get_performance(project_id, adapter_id)

    selected_kpis = [
        kpi_to_select for kpi_to_select in performance.kpis if kpi_to_select.name == kpi
    ]
    if not selected_kpis:
        raise HTTPException(404, f"KPI {kpi} not found in performance of adapter {adapter_id} in project {project_id}")
    return selected_kpis


@router.get(
    "/events",
    response_model=List[performance_data.Event]
)
async def get_events(project_id: str, adapter_id: str, num_events: int = 10, offset: int = 0):
    performance = prodsys_backend.get_performance(project_id, adapter_id)
    if offset + num_events > len(performance.event_log):
        raise HTTPException(404, f"Only {len(performance.event_log)} events found. Offset {offset} and num_events {num_events} are too large.")
    return performance.event_log[offset:offset+num_events]
