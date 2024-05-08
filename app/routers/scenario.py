from typing import List, Annotated


from fastapi import APIRouter, Body
from pydantic import BaseModel


from prodsys.models import scenario_data, performance_indicators
from app.dao import scenario_dao


class UserSettingsIn(BaseModel):

    class Config:
        use_enum_values = True


SCENARIO_EXAMPLE = scenario_data.ScenarioData.Config.schema_extra["example"]["value"]
SCENARIO_CONSTRAINT_EXAMPLE = scenario_data.ScenarioConstrainsData.Config.schema_extra[
    "example"
]["value"]
SCENARIO_OPTIONS_EXAMPLE = scenario_data.ScenarioOptionsData.Config.schema_extra[
    "example"
]["value"]
SCENARIO_INFO_EXAMPLE = scenario_data.ScenarioInfoData.Config.schema_extra["example"][
    "value"
]
OBJECTIVES_LIST_EXAMPLE = [
    item for item in scenario_data.Objective.Config.schema_extra["examples"]
]

router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/scenario",
    tags=["scenario"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/",
    response_model=scenario_data.ScenarioData,
    responses={
        200: {
            "description": "Sucessfully returned scenario",
            "content": {"application/json": {"example": SCENARIO_EXAMPLE}},
        },
        404: {"description": "No scenario found"},
    },
)
async def get_scenario(project_id: str, adapter_id: str) -> scenario_data.ScenarioData:
    return scenario_dao.get(project_id, adapter_id)


@router.put(
    "/",
    response_model=scenario_data.ScenarioData,
    responses={
        200: {
            "description": "Sucessfully updated scenario",
            "content": {"application/json": {"example": SCENARIO_EXAMPLE}},
        },
        404: {"description": "No resources found"},
    },
)
async def update_scenario(
    project_id: str,
    adapter_id: str,
    scenario: Annotated[scenario_data.ScenarioData, Body(example=SCENARIO_EXAMPLE)],
) -> scenario_data.ScenarioData:
    return scenario_dao.update(project_id, adapter_id, scenario)


@router.get(
    "/contraints",
    response_model=scenario_data.ScenarioConstrainsData,
    responses={
        200: {
            "description": "Sucessfully returned scenario constraints",
            "content": {"application/json": {"example": SCENARIO_CONSTRAINT_EXAMPLE}},
        },
        404: {"description": "No scenario constraints found"},
    },
)
async def get_scenario_constrains(project_id: str, adapter_id: str):
    return scenario_dao.get_constraints(project_id, adapter_id)


@router.put(
    "/constraints",
    response_model=scenario_data.ScenarioData,
    responses={
        200: {
            "description": "Sucessfully updated scenario constraints",
            "content": {"application/json": {"example": SCENARIO_EXAMPLE}},
        },
        404: {"description": "No scenario found"},
    },
)
async def update_scenario_constrains(
    project_id: str,
    adapter_id: str,
    constrains: Annotated[
        scenario_data.ScenarioConstrainsData, Body(example=SCENARIO_CONSTRAINT_EXAMPLE)
    ],
) -> scenario_data.ScenarioConstrainsData:
    return scenario_dao.update_constraints(project_id, adapter_id, constrains)


@router.get(
    "/info",
    response_model=scenario_data.ScenarioInfoData,
    responses={
        200: {
            "description": "Sucessfully returned scenario info",
            "content": {"application/json": {"example": SCENARIO_INFO_EXAMPLE}},
        },
        404: {"description": "No scenario found"},
    },
)
async def get_scenario_info(project_id: str, adapter_id: str):
    return scenario_dao.get_info(project_id, adapter_id)


@router.put(
    "/info",
    response_model=scenario_data.ScenarioData,
    responses={
        200: {
            "description": "Sucessfully updated scenario info",
            "content": {"application/json": {"example": SCENARIO_EXAMPLE}},
        },
        404: {"description": "No scenario found"},
    },
)
async def update_scenario_info(
    project_id: str,
    adapter_id: str,
    info: Annotated[
        scenario_data.ScenarioInfoData, Body(example=SCENARIO_INFO_EXAMPLE)
    ],
) -> scenario_data.ScenarioData:
    return scenario_dao.update_info(project_id, adapter_id, info)


@router.get(
    "/options",
    response_model=scenario_data.ScenarioOptionsData,
    responses={
        200: {
            "description": "Sucessfully returned scenario options",
            "content": {"application/json": {"example": SCENARIO_OPTIONS_EXAMPLE}},
        },
        404: {"description": "No scenario found"},
    },
)
async def get_scenario_options(project_id: str, adapter_id: str):
    return scenario_dao.get_options(project_id, adapter_id)


@router.put(
    "/options",
    response_model=scenario_data.ScenarioData,
    responses={
        200: {
            "description": "Sucessfully updated scenario options",
            "content": {"application/json": {"example": SCENARIO_EXAMPLE}},
        },
        404: {"description": "No scenario found"},
    },
)
async def update_scenario_options(
    project_id: str,
    adapter_id: str,
    options: Annotated[
        scenario_data.ScenarioOptionsData, Body(example=SCENARIO_OPTIONS_EXAMPLE)
    ],
) -> scenario_data.ScenarioData:
    return scenario_dao.update_options(project_id, adapter_id, options)


@router.get(
    "/objectives",
    response_model=List[scenario_data.Objective],
    responses={
        200: {
            "description": "Sucessfully returned objectives",
            "content": {"application/json": {"example": OBJECTIVES_LIST_EXAMPLE}},
        },
        404: {"description": "No objectives found"},
    },
)
async def get_scenario_objectives(project_id: str, adapter_id: str):
    return scenario_dao.get_objectives(project_id, adapter_id)


@router.put(
    "/objectives",
    response_model=scenario_data.ScenarioData,
    responses={
        200: {
            "description": "Sucessfully updated objectives",
            "content": {"application/json": {"example": SCENARIO_EXAMPLE}},
        },
        404: {"description": "No scenario found"},
    },
)
async def update_scenario_objectives(
    project_id: str,
    adapter_id: str,
    objectives: Annotated[
        List[scenario_data.Objective], Body(example=OBJECTIVES_LIST_EXAMPLE)
    ],
) -> scenario_data.ScenarioData:
    return scenario_dao.update_objectives(project_id, adapter_id, objectives)


@router.post(
    "/objectives/objective",
    response_model=scenario_data.ScenarioData,
    responses={
        200: {
            "description": "Sucessfully added objective",
            "content": {"application/json": {"example": SCENARIO_EXAMPLE}},
        },
        404: {"description": "No scenario found"},
    },
)
async def create_scenario_objective(
    project_id: str, adapter_id: str, objective: scenario_data.Objective
):
    return scenario_dao.add_objective(project_id, adapter_id, objective)


@router.put(
    "/objectives/objective",
    response_model=scenario_data.ScenarioData,
    responses={
        200: {
            "description": "Sucessfully updated objectives",
            "content": {"application/json": {"example": SCENARIO_EXAMPLE}},
        },
        404: {"description": "No scenario found"},
    },
)
async def update_scenario_objective(
    project_id: str, adapter_id: str, objective: scenario_data.Objective
):
    return scenario_dao.update_objective(project_id, adapter_id, objective)


@router.delete(
    "/objectives/objective/{objective_name}",
    response_model=scenario_data.ScenarioData,
    responses={
        200: {
            "description": "Sucessfully deleted objective",
            "content": {"application/json": {"example": SCENARIO_EXAMPLE}},
        },
        404: {"description": "No scenario found"},
    },
)
async def delete_scenario_objective(
    project_id: str, adapter_id: str, objective_name: performance_indicators.KPIEnum
):
    return scenario_dao.delete_objective(project_id, adapter_id, objective_name)
