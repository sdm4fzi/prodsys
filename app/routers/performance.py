from typing import List


from fastapi import APIRouter, HTTPException


from prodsys.models import performance_data, performance_indicators
from app.dependencies import prodsys_backend

KPI_EXAMPLES = {
    "Output": performance_indicators.Output.model_config["json_schema_extra"]["examples"],
    "Throughput": performance_indicators.Throughput.model_config["json_schema_extra"]["examples"],
    "Cost": performance_indicators.Cost.model_config["json_schema_extra"]["examples"],
    "WIP": performance_indicators.WIP.model_config["json_schema_extra"]["examples"],
    "ThroughputTime": performance_indicators.ThroughputTime.model_config["json_schema_extra"][
        "examples"
    ],
    "ProcessingTime": performance_indicators.ProcessingTime.model_config["json_schema_extra"][
        "examples"
    ],
    "ProductiveTime": performance_indicators.ProductiveTime.model_config["json_schema_extra"][
        "examples"
    ],
    "StandbyTime": performance_indicators.StandbyTime.model_config["json_schema_extra"]["examples"],
    "SetupTime": performance_indicators.SetupTime.model_config["json_schema_extra"]["examples"],
    "UnscheduledDowntime": performance_indicators.UnscheduledDowntime.model_config["json_schema_extra"][
        "examples"
    ],
    "DynamicWIP": performance_indicators.DynamicWIP.model_config["json_schema_extra"]["examples"],
    "DynamicThroughputTime": performance_indicators.DynamicThroughputTime.model_config["json_schema_extra"][
        "examples"
    ],
}

KPI_LIST_EXAMPLE = [item for item in KPI_EXAMPLES.values()]


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
            "content": {"application/json": {"example": KPI_LIST_EXAMPLE}},
        },
        404: {"description": "No KPIs found"},
    },
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
            "content": {"application/json": {"examples": KPI_EXAMPLES}},
        },
        404: {"description": "No KPIs found"},
    },
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
        raise HTTPException(
            404,
            f"KPI {kpi} not found in performance of adapter {adapter_id} in project {project_id}",
        )
    return selected_kpis


@router.get("/events", response_model=List[performance_data.Event])
async def get_events(
    project_id: str, adapter_id: str, num_events: int = 10, offset: int = 0
):
    performance = prodsys_backend.get_performance(project_id, adapter_id)
    if offset + num_events > len(performance.event_log):
        raise HTTPException(
            404,
            f"Only {len(performance.event_log)} events found. Offset {offset} and num_events {num_events} are too large.",
        )
    return performance.event_log[offset : offset + num_events]
