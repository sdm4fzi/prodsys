

from sqlite3 import adapt
from typing import Optional
from fastapi import APIRouter, BackgroundTasks


from app.models.progress_report import ProgressReport
from app.dependencies import run_simulation, get_progress_of_simulation, prodsys_backend

router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/simulate",
    tags=["simulation"],
    responses={404: {"description": "Not found"}},
)

@router.get(
    "/",
    response_model=str,
)
async def simulate(project_id: str, adapter_id: str, run_length: Optional[float], background_tasks: BackgroundTasks, seed: Optional[int]=0):
    if not run_length:
        adapter = prodsys_backend.get_adapter(project_id, adapter_id)
        if adapter.scenario_data and adapter.scenario_data.info:
            run_length = adapter.scenario_data.info.time_range
        else:
            run_length = 1440
    background_tasks.add_task(run_simulation, project_id, adapter_id, run_length, seed)
    return f"Sucessfully started simulation for {run_length} minutes for adapter with ID: {adapter_id}"

@router.get(
    "/progress",
    response_model=ProgressReport,
)
async def get_simulation_progress(project_id: str, adapter_id: str) -> ProgressReport:
    return get_progress_of_simulation(project_id, adapter_id)
    
    