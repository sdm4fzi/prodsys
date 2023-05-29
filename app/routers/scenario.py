from typing import List, Annotated, Dict, Optional


from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field


from prodsys.models import (
    scenario_data,
    performance_indicators
)
from app.dependencies import get_adapter

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
async def read_scenario(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(404, "No scenario found.")
    return adapter.scenario_data


@router.put("/")
async def create_scenario(
    project_id: str,
    adapter_id: str,
    scenario: scenario_data.ScenarioData,
):
    adapter = get_adapter(project_id, adapter_id)
    adapter.scenario_data = scenario
    return "Sucessfully created scenario"


@router.get("/contraints",
           response_model=scenario_data.ScenarioConstrainsData,
           )
async def read_scenario_constrains(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(404, "No scenario found.")
    return adapter.scenario_data.constraints

@router.put("/constraints")
async def create_scenario_constrains(
    project_id: str,
    adapter_id: str,
    constrains: scenario_data.ScenarioConstrainsData,
):
    adapter = get_adapter(project_id, adapter_id)
    return_string = ""
    if not adapter.scenario_data:
        adapter.scenario_data = scenario_data.ScenarioData(**scenario_data.ScenarioData.Config.schema_extra["example"]["value"])
        return_string = "Initialized scenario with default values for scenario info, options and objectives."
    adapter.scenario_data.constraints = constrains
    return "Sucessfully created scenario constrains. " + return_string


@router.get("/info",
              response_model=scenario_data.ScenarioInfoData,
                )
async def read_scenario_info(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(404, "No scenario found.")
    return adapter.scenario_data.info

@router.put("/info")
async def create_scenario_info(
    project_id: str,
    adapter_id: str,
    info: scenario_data.ScenarioInfoData,
):
    adapter = get_adapter(project_id, adapter_id)
    return_string = ""
    if not adapter.scenario_data:
        adapter.scenario_data = scenario_data.ScenarioData(**scenario_data.ScenarioData.Config.schema_extra["example"]["value"])
        return_string = "Initialized scenario with default values for scenario constrains, options and objectives."
    adapter.scenario_data.info = info
    return "Sucessfully created scenario info. " + return_string

@router.get("/options",
                response_model=scenario_data.ScenarioOptionsData,
                )
async def read_scenario_options(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(404, "No scenario found.")
    return adapter.scenario_data.options

@router.put("/options")
async def create_scenario_options(
    project_id: str,
    adapter_id: str,
    options: scenario_data.ScenarioOptionsData,
):
    adapter = get_adapter(project_id, adapter_id)
    return_string = ""
    if not adapter.scenario_data:
        adapter.scenario_data = scenario_data.ScenarioData(**scenario_data.ScenarioData.Config.schema_extra["example"]["value"])
        return_string = "Initialized scenario with default values for scenario constrains, info and objectives."
    adapter.scenario_data.options = options
    return "Sucessfully created scenario options. " + return_string


OBJECTIVES_LIST_EXAMPLE = [item["value"] for item in scenario_data.Objectives.Config.schema_extra["examples"].values()]


@router.get("/objectives",
                response_model=List[scenario_data.Objectives],
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
async def read_scenario_objectives(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(404, "No scenario found.")
    return adapter.scenario_data.objectives   

@router.put("/objectives")
async def create_scenario_objectives(
    project_id: str,
    adapter_id: str,
    objectives: Annotated[List[scenario_data.Objectives], Body(example=OBJECTIVES_LIST_EXAMPLE)],
):
    adapter = get_adapter(project_id, adapter_id)
    return_string = ""
    if not adapter.scenario_data:
        adapter.scenario_data = scenario_data.ScenarioData(**scenario_data.ScenarioData.Config.schema_extra["example"]["value"])
        return_string = "Initialized scenario with default values for scenario constrains, info and options."
    adapter.scenario_data.objectives = objectives
    return "Sucessfully created scenario objectives. " + return_string
