from typing import List, Annotated


from fastapi import APIRouter, HTTPException, Body


from prodsys.models import (
    time_model_data,
)
from app.dependencies import get_adapter, get_time_model

TIME_MODEL_EXAMPLES = {
            "Sequential time model": time_model_data.SequentialTimeModelData.Config.schema_extra["example"],	
            "Functional time model": time_model_data.FunctionTimeModelData.Config.schema_extra["example"],
            "Manhattan Distance time model": time_model_data.ManhattanDistanceTimeModelData.Config.schema_extra["example"]
        }

TIME_MODEL_LIST_EXAMPLE = [item["value"] for item in TIME_MODEL_EXAMPLES.values()]


router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/time_models",
    tags=["time_models"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/",
    response_model=List[time_model_data.TIME_MODEL_DATA],
    responses={
        200: {
            "description": "Sucessfully returned time models",
            "content": {
                "application/json": {
                    "example": TIME_MODEL_LIST_EXAMPLE
        }
            },
        },
        404: {"description": "No time models found."},
    }
)
async def read_time_models(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.time_model_data

@router.put("/{time_model_id}")
async def create_time_model(
    project_id: str,
    adapter_id: str,
    time_model_id,
    time_model: Annotated[
        time_model_data.TIME_MODEL_DATA,
        Body(examples=TIME_MODEL_EXAMPLES)
    ],
):
    if time_model.ID != time_model_id:
        raise HTTPException(404, "Time model ID must not be changed")
    adapter = get_adapter(project_id, adapter_id)
    adapter.time_model_data.append(time_model)
    return "Sucessfully created time model with ID: " + time_model.ID

@router.get(
    "/{time_model_id}",
    response_model=time_model_data.TIME_MODEL_DATA,
    responses={
        200: {
            "description": "Sucessfully returned time model",
            "content": {
                "application/json": {
                    "examples":
                        TIME_MODEL_EXAMPLES
                }
            },
        },
        404: {"description": "Time model not found"},
    }
)
async def read_time_model(project_id: str, adapter_id: str, time_model_id: str):
    time_model = get_time_model(project_id, adapter_id, time_model_id)
    return time_model
