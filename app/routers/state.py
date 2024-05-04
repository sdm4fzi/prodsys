from typing import List, Annotated, Dict


from fastapi import APIRouter, HTTPException, Body


from prodsys.models import (
    state_data,
)
from app.dependencies import prodsys_backend, get_state_from_backend

STATE_DATA_EXAMPLES = {
    state_data.StateTypeEnum.BreakDownState: state_data.BreakDownStateData.Config.schema_extra[
        "example"
    ],
    state_data.StateTypeEnum.ProductionState: state_data.ProductionStateData.Config.schema_extra[
        "example"
    ],
    state_data.StateTypeEnum.TransportState: state_data.TransportStateData.Config.schema_extra[
        "example"
    ],
    state_data.StateTypeEnum.ProcessBreakDownState: state_data.ProcessBreakDownStateData.Config.schema_extra[
        "example"
    ],
    state_data.StateTypeEnum.SetupState: state_data.SetupStateData.Config.schema_extra[
        "example"
    ],
}

STATE_LIST_EXAMPLE = [item["value"] for item in STATE_DATA_EXAMPLES.values()]

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
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    return adapter.state_data


@router.post("/",
            response_model=state_data.STATE_DATA_UNION,
            responses={
                200: {
                    "description": "Sucessfully updated state",
                    "content": {"application/json": {"examples": STATE_DATA_EXAMPLES}},
                },
                404: {"description": "No state found."},
            })
async def create_state(
    project_id: str,
    adapter_id: str,
    state: Annotated[state_data.STATE_DATA_UNION, Body(examples=STATE_LIST_EXAMPLE)],
):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    # TODO: only add if state does not exist, else raise error
    adapter.state_data.append(state)
    prodsys_backend.update_adapter(project_id, adapter)
    return state


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
    state = get_state_from_backend(project_id, adapter_id, state_id)
    return state


@router.put("/{state_id}",
            response_model=state_data.STATE_DATA_UNION,
            responses={
                200: {
                    "description": "Sucessfully updated state",
                    "content": {"application/json": {"examples": STATE_DATA_EXAMPLES}},
                },
                404: {"description": "No state found."},
            })
async def update_state(
    project_id: str,
    adapter_id: str,
    state_id,
    state: Annotated[state_data.STATE_DATA_UNION, Body(examples=STATE_LIST_EXAMPLE)],
):
    if state.ID != state_id:
        raise HTTPException(404, "State ID must not be changed")
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    # TODO: make removal of old state 
    adapter.state_data.append(state)
    prodsys_backend.update_adapter(project_id, adapter)
    return state

@router.delete("/{state_id}")
async def delete_state(project_id: str, adapter_id: str, state_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    state = get_state_from_backend(project_id, adapter_id, state_id)
    adapter.state_data.remove(state)
    return "Sucessfully deleted state with ID: " + state_id