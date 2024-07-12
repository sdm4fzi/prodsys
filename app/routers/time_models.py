from typing import List, Annotated


from fastapi import APIRouter, Body


from app.dao import time_model_dao
from prodsys.models import (
    time_model_data,
)

TIME_MODEL_EXAMPLES = {
    "Sample time model": time_model_data.SampleTimeModelData.model_config["json_schema_extra"][
        "examples"
    ],
    "Scheduled time model": time_model_data.ScheduledTimeModelData.model_config["json_schema_extra"][
        "examples"
    ],
    "Functional time model": time_model_data.FunctionTimeModelData.model_config["json_schema_extra"][
        "examples"
    ],
    "Distance time model": time_model_data.DistanceTimeModelData.model_config["json_schema_extra"][
        "examples"
    ],
}

TIME_MODEL_LIST_EXAMPLE = [item for item in TIME_MODEL_EXAMPLES.values()]


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
            "content": {"application/json": {"example": TIME_MODEL_LIST_EXAMPLE}},
        },
        404: {"description": "No time models found."},
    },
)
async def get_time_models(project_id: str, adapter_id: str):
    return time_model_dao.get_all(project_id, adapter_id)


@router.post(
    "/",
    response_model=time_model_data.TIME_MODEL_DATA,
    responses={
        200: {
            "description": "Sucessfully created time model",
            "content": {"application/json": {"examples": TIME_MODEL_EXAMPLES}},
        }
    },
)
async def create_time_model(
    project_id: str,
    adapter_id: str,
    time_model: Annotated[
        time_model_data.TIME_MODEL_DATA, Body(examples=TIME_MODEL_LIST_EXAMPLE)
    ],
):
    return time_model_dao.add(project_id, adapter_id, time_model)


@router.get(
    "/{time_model_id}",
    response_model=time_model_data.TIME_MODEL_DATA,
    responses={
        200: {
            "description": "Sucessfully returned time model",
            "content": {"application/json": {"examples": TIME_MODEL_EXAMPLES}},
        },
        404: {"description": "Time model not found"},
    },
)
async def get_time_model(project_id: str, adapter_id: str, time_model_id: str):
    return time_model_dao.get(project_id, adapter_id, time_model_id)


@router.put(
    "/{time_model_id}",
    response_model=time_model_data.TIME_MODEL_DATA,
    responses={
        200: {
            "description": "Sucessfully updated time model",
            "content": {"application/json": {"examples": TIME_MODEL_EXAMPLES}},
        },
        404: {"description": "Time model not found"},
    },
)
async def update_time_model(
    project_id: str,
    adapter_id: str,
    time_model_id,
    time_model: Annotated[
        time_model_data.TIME_MODEL_DATA, Body(examples=TIME_MODEL_LIST_EXAMPLE)
    ],
):
    return time_model_dao.update(project_id, adapter_id, time_model_id, time_model)


@router.delete("/{time_model_id}", response_model=str)
async def delete_time_model(project_id: str, adapter_id: str, time_model_id: str):
    time_model_dao.delete(project_id, adapter_id, time_model_id)
    return f"Succesfully deleted time model with ID {time_model_id}"
