from typing import List, Annotated


from fastapi import APIRouter, Body


from prodsys.models import (
    state_data,
)
from app.dao import state_dao

STATE_DATA_EXAMPLES = {
    state_data.StateTypeEnum.BreakDownState: state_data.BreakDownStateData.model_config["json_schema_extra"]["examples"],
    state_data.StateTypeEnum.ProductionState: state_data.ProductionStateData.model_config["json_schema_extra"]["examples"],
    state_data.StateTypeEnum.TransportState: state_data.TransportStateData.model_config["json_schema_extra"]["examples"],
    state_data.StateTypeEnum.ProcessBreakDownState: state_data.ProcessBreakDownStateData.model_config["json_schema_extra"]["examples"],
    state_data.StateTypeEnum.SetupState: state_data.SetupStateData.model_config["json_schema_extra"]["examples"],
}

STATE_LIST_EXAMPLE = [item for item in STATE_DATA_EXAMPLES.values()]

router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/states",
    tags=["states"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/",
    response_model=List[state_data.STATE_DATA_UNION],
    responses={
        200: {
            "description": "Sucessfully returned states",
            "content": {"application/json": {"example": STATE_LIST_EXAMPLE}},
        },
        404: {"description": "No states found."},
    },
)
async def get_states(project_id: str, adapter_id: str):
    return state_dao.get_all(project_id, adapter_id)


@router.post(
    "/",
    response_model=state_data.STATE_DATA_UNION,
    responses={
        200: {
            "description": "Sucessfully updated state",
            "content": {"application/json": {"examples": STATE_DATA_EXAMPLES}},
        },
        404: {"description": "No state found."},
    },
)
async def create_state(
    project_id: str,
    adapter_id: str,
    state: Annotated[state_data.STATE_DATA_UNION, Body(examples=STATE_LIST_EXAMPLE)],
):
    return state_dao.add(project_id, adapter_id, state)


@router.get(
    "/{state_id}",
    response_model=state_data.STATE_DATA_UNION,
    responses={
        200: {
            "description": "Sucessfully returned state",
            "content": {"application/json": {"examples": STATE_DATA_EXAMPLES}},
        },
        404: {"description": "No state found."},
    },
)
async def get_state(project_id: str, adapter_id: str, state_id: str):
    return state_dao.get(project_id, adapter_id, state_id)


@router.put(
    "/{state_id}",
    response_model=state_data.STATE_DATA_UNION,
    responses={
        200: {
            "description": "Sucessfully updated state",
            "content": {"application/json": {"examples": STATE_DATA_EXAMPLES}},
        },
        404: {"description": "No state found."},
    },
)
async def update_state(
    project_id: str,
    adapter_id: str,
    state_id,
    state: Annotated[state_data.STATE_DATA_UNION, Body(examples=STATE_LIST_EXAMPLE)],
):
    return state_dao.update(project_id, adapter_id, state_id, state)


@router.delete("/{state_id}", response_model=str)
async def delete_state(project_id: str, adapter_id: str, state_id: str):
    state_dao.delete(project_id, adapter_id, state_id)
    return f"Succesfully deleted state with ID {state_id}."
