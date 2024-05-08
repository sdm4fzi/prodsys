from typing import List, Annotated


from fastapi import APIRouter, Body


from prodsys.models import (
    sink_data,
)
from app.dao import sink_dao

SINK_LIST_EXAMPLE = [sink_data.SinkData.Config.schema_extra["example"]["value"]]


router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/sinks",
    tags=["sinks"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/",
    response_model=List[sink_data.SinkData],
    responses={
        200: {
            "description": "Succesfully returned sink data",
            "content": {"application/json": {"example": SINK_LIST_EXAMPLE}},
        },
        404: {"description": "No sink data found."},
    },
)
async def get_sinks(project_id: str, adapter_id: str):
    return sink_dao.get_all(project_id, adapter_id)


@router.post(
    "/",
    response_model=sink_data.SinkData,
    responses={
        200: {
            "description": "Successfully created sink data",
            "content": {"application/json": sink_data.SinkData.Config.schema_extra},
        }
    },
)
async def create_sink(
    project_id: str,
    adapter_id: str,
    sink: Annotated[
        sink_data.SinkData,
        Body(example=sink_data.SinkData.Config.schema_extra["example"]),
    ],
) -> sink_data.SinkData:
    return sink_dao.add(project_id, adapter_id, sink)


@router.get(
    "/{sink_id}",
    response_model=sink_data.SinkData,
    responses={
        200: {
            "description": "Successfulle returned sink data.",
            "content": {"application/json": sink_data.SinkData.Config.schema_extra},
        },
        404: {"description": "Sink not found."},
    },
)
async def get_sink(project_id: str, adapter_id: str, sink_id: str):
    return sink_dao.get(project_id, adapter_id, sink_id)


@router.put(
    "/{sink_id}",
    response_model=sink_data.SinkData,
    responses={
        200: {
            "description": "Successfully updated sink data",
            "content": {"application/json": sink_data.SinkData.Config.schema_extra},
        },
        404: {"description": "Sink not found."},
    },
)
async def create_sink(
    project_id: str,
    adapter_id: str,
    sink_id: str,
    sink: Annotated[
        sink_data.SinkData,
        Body(example=sink_data.SinkData.Config.schema_extra["example"]),
    ],
) -> sink_data.SinkData:
    return sink_dao.update(project_id, adapter_id, sink_id, sink)


@router.delete("/{sink_id}", response_model=str)
async def delete_sink(project_id: str, adapter_id: str, sink_id: str):
    sink_dao.delete(project_id, adapter_id, sink_id)
    return f"Succesfully deleted sink with id {sink_id}."
