

from fastapi import APIRouter


from prodsys.models import (
    scenario_data
)
from app.dependencies import get_adapter, evaluate

router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/simulate",
    tags=["simulation"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/",
    response_model=str,
)
async def run_simulation(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    evaluate(adapter)
    return "Sucessfully ran simulation for adapter with ID: " + adapter_id

@router.post(
    "/",
    response_model=str,
)
async def run_simulation(project_id: str, adapter_id: str, time_range: int):
    adapter = get_adapter(project_id, adapter_id)	
    adapter.scenario_data = scenario_data.ScenarioData(**scenario_data.ScenarioData.Config.schema_extra["example"]["value"])
    adapter.scenario_data.info.time_range = time_range
    evaluate(adapter)
    adapter.scenario_data = None
    return f"Sucessfully ran simulation for {time_range} minutes for adapter with ID: " + adapter_id