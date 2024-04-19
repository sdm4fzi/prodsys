from typing import List, Annotated


from fastapi import APIRouter, HTTPException, Body


from prodsys.models import (
    sink_data,
)
from app.dependencies import prodsys_backend, get_sink_from_backend

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
            "content": {
                "application/json": {
                    "example": SINK_LIST_EXAMPLE
                }
            }
        },
        404: {"description": "No sink data found."}
    }
)
async def get_sinks(project_id: str, adapter_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    return adapter.sink_data


@router.post("/", 
             response_model=sink_data.SinkData, 
             responses={
                 200: {
                     "description": "Successfully created sink data",
                     "content": {
                         "application/json": sink_data.SinkData.Config.schema_extra
                     }
                 }
             })
async def create_sink(
    project_id: str,
    adapter_id: str,
    sink: Annotated[sink_data.SinkData,
                    Body(example=sink_data.SinkData.Config.schema_extra["example"])]
) -> sink_data.SinkData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    # TODO: only add if sink does not exist, else raise error
    adapter.sink_data.append(sink)
    prodsys_backend.update_adapter(project_id, adapter)
    return sink


@router.get(
    "/{sink_id}",
    response_model=sink_data.SinkData,
    responses={
        200: {
            "description": "Successfulle returned sink data.",
            "content": {
                "application/json": sink_data.SinkData.Config.schema_extra
            }
        },
        404: {"description": "Sink not found."}
    }
)
async def get_sink(project_id: str, adapter_id: str, sink_id: str):
    sink = get_sink_from_backend(project_id, adapter_id, sink_id)
    return sink


@router.put("/{sink_id}", 
            response_model=sink_data.SinkData,
            responses={
                200: {
                    "description": "Successfully updated sink data",
                    "content": {
                        "application/json": sink_data.SinkData.Config.schema_extra
                    }
                },
                404: {"description": "Sink not found."}
            })
async def create_sink(
    project_id: str,
    adapter_id: str,
    sink_id: str,
    sink: Annotated[sink_data.SinkData,
                    Body(example=sink_data.SinkData.Config.schema_extra["example"])]
) -> sink_data.SinkData:
    if sink.ID != sink_id:
        raise HTTPException(404, "Sink ID must not be changed")
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    # TODO: only add if sink does not exist, else raise error
    adapter.sink_data.append(sink)
    return sink

@router.delete("/{sink_id}")
async def delete_sink(project_id: str, adapter_id: str, sink_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    sink = get_sink_from_backend(project_id, adapter_id, sink_id)
    adapter.sink_data.remove(sink)
    return "Sucessfully deleted sink with ID: " + sink_id