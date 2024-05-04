from typing import List, Annotated, Dict, Optional


from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field


from prodsys.models import (
    scenario_data,
    performance_indicators
)
from app.dependencies import prodsys_backend

class UserSettingsIn(BaseModel):

    class Config:
        use_enum_values = True



router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/scenario",
    tags=["scenario"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/",
    response_model=scenario_data.ScenarioData
)
async def get_scenario(project_id: str, adapter_id: str) -> scenario_data.ScenarioData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(404, "No scenario found.")
    return adapter.scenario_data

@router.put("/", response_model=scenario_data.ScenarioData)
async def update_scenario(
    project_id: str,
    adapter_id: str,
    scenario: scenario_data.ScenarioData,
) -> scenario_data.ScenarioData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    adapter.scenario_data = scenario
    prodsys_backend.update_adapter(project_id, adapter)
    return scenario


@router.get("/contraints",
           response_model=scenario_data.ScenarioConstrainsData,
           )
async def get_scenario_constrains(project_id: str, adapter_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(404, "No scenario found.")
    return adapter.scenario_data.constraints

@router.put("/constraints", response_model=scenario_data.ScenarioConstrainsData)
async def update_scenario_constrains(
    project_id: str,
    adapter_id: str,
    constrains: scenario_data.ScenarioConstrainsData,
) -> scenario_data.ScenarioConstrainsData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(404, f"No scenario found for adapter {adapter_id} in project {project_id}.")
    adapter.scenario_data.constraints = constrains
    prodsys_backend.update_adapter(project_id, adapter)
    return constrains


@router.get("/info",
              response_model=scenario_data.ScenarioInfoData,
                )
async def get_scenario_info(project_id: str, adapter_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(404, "No scenario found.")
    return adapter.scenario_data.info

@router.put("/info")
async def update_scenario_info(
    project_id: str,
    adapter_id: str,
    info: scenario_data.ScenarioInfoData,
):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(404, f"No scenario found for adapter {adapter_id} in project {project_id}.")
    adapter.scenario_data.info = info
    prodsys_backend.update_adapter(project_id, adapter)
    return info

@router.get("/options",
                response_model=scenario_data.ScenarioOptionsData,
                )
async def get_scenario_options(project_id: str, adapter_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(404, "No scenario found.")
    prodsys_backend.update_adapter(project_id, adapter)
    return adapter.scenario_data.options

@router.put("/options")
async def update_scenario_options(
    project_id: str,
    adapter_id: str,
    options: scenario_data.ScenarioOptionsData,
) -> scenario_data.ScenarioOptionsData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(404, f"No scenario found for adapter {adapter_id} in project {project_id}.")
    adapter.scenario_data.options = options
    prodsys_backend.update_adapter(project_id, adapter)
    return options

OBJECTIVES_LIST_EXAMPLE = [item for item in scenario_data.Objective.Config.schema_extra["examples"]]

@router.get("/objectives",
                response_model=List[scenario_data.Objective],
                responses={
                    200: {
                        "description": "Sucessfully returned objectives",
                        "content": {
                            "application/json": {
                                "example": OBJECTIVES_LIST_EXAMPLE
                    }
                        },
                    },
                    404: {"description": "No objectives found"},
                }
                )
async def get_scenario_objectives(project_id: str, adapter_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(404, "No scenario found.")
    return adapter.scenario_data.objectives   

@router.put("/objectives")
async def update_scenario_objectives(
    project_id: str,
    adapter_id: str,
    objectives: Annotated[List[scenario_data.Objective], Body(example=OBJECTIVES_LIST_EXAMPLE)],
) -> List[scenario_data.Objective]:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(404, f"No scenario found for adapter {adapter_id} in project {project_id}.")
    adapter.scenario_data.objectives = objectives
    prodsys_backend.update_adapter(project_id, adapter)
    return objectives
