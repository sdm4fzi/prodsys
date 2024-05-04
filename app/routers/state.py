from typing import List, Annotated, Dict


from fastapi import APIRouter, HTTPException, Body


from prodsys.models import (
    state_data,
)
from app.dependencies import get_adapter, get_state

# TIME_MODEL_EXAMPLES = {
#             "Sequential time model": time_model_data.SequentialTimeModelData.Config.schema_extra["example"],
#             "Functional time model": time_model_data.FunctionTimeModelData.Config.schema_extra["example"],
#             "Manhattan Distance time model": time_model_data.ManhattanDistanceTimeModelData.Config.schema_extra["example"]
#         }

# TIME_MODEL_LIST_EXAMPLE = [item["value"] for item in TIME_MODEL_EXAMPLES.values()]

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
async def read_states(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.state_data


@router.put("/{state_id}")
async def create_state(
    project_id: str,
    adapter_id: str,
    state_id,
    state: Annotated[state_data.STATE_DATA_UNION, Body(examples=STATE_DATA_EXAMPLES)],
):
    if state.ID != state_id:
        raise HTTPException(404, "State ID must not be changed")
    adapter = get_adapter(project_id, adapter_id)
    adapter.state_data.append(state)
    return "Sucessfully created state with ID: " + state.ID


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
async def read_state(project_id: str, adapter_id: str, state_id: str):
    state = get_state(project_id, adapter_id, state_id)
    return state
