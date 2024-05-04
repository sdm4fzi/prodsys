from typing import List, Annotated


from fastapi import APIRouter, HTTPException, Body


from prodsys.models import (
    source_data
)
from app.dependencies import prodsys_backend, get_source_from_backend

SOURCE_LIST_EXAMPLE = [source_data.SourceData.Config.schema_extra["example"]["value"]]


router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/sources",
    tags=["sources"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/",
    response_model=List[source_data.SourceData],
    responses={
        200: {
            "description": "Succesfully returned source data",
            "content": {
                "application/json": {
                    "example": SOURCE_LIST_EXAMPLE
                }
            }
        },
        404: {"description": "No source data found."}
    }
)
async def get_sources(project_id: str, adapter_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    return adapter.source_data


@router.post("/",
            response_model=source_data.SourceData,
            responses={
                200: {
                    "description": "Successfully updated source data",
                    "content": {
                        "application/json": SOURCE_LIST_EXAMPLE
                    }
                }
            })
async def create_sink(
    project_id: str,
    adapter_id: str,
    source: Annotated[source_data.SourceData,
                    Body(example=source_data.SourceData.Config.schema_extra["example"])]
):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    # TODO: only add if sink does not exist, else raise error
    adapter.source_data.append(source)
    prodsys_backend.update_adapter(project_id, adapter)
    return source


@router.get(
    "/{source_id}",
    response_model=source_data.SourceData,
    responses={
        200: {
            "description": "Successfulle returned source data.",
            "content": {
                "application/json": source_data.SourceData.Config.schema_extra
            }
        },
        404: {"description": "Sink not found."}
    }
)
async def get_source(project_id: str, adapter_id: str, source_id: str):
    source = get_source_from_backend(project_id, adapter_id, source_id)
    return source


@router.put("/{source_id}",
            response_model=source_data.SourceData,
            responses={
                200: {
                    "description": "Successfully updated source data",
                    "content": {
                        "application/json": SOURCE_LIST_EXAMPLE
                    }
                }
            })
async def update_source(
    project_id: str,
    adapter_id: str,
    source_id: str,
    source: Annotated[source_data.SourceData,
                    Body(example=source_data.SourceData.Config.schema_extra["example"])]
):
    if source.ID != source_id:
        raise HTTPException(404, "Source ID must not be changed")
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    # TODO: only add if sink does not exist, else raise error
    adapter.source_data.append(source)
    prodsys_backend.update_adapter(project_id, adapter)
    return source

@router.delete("/{source_id}")
async def delete_source(project_id: str, adapter_id: str, source_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    source = get_source_from_backend(project_id, adapter_id, source_id)
    adapter.source_data.remove(source)
    return "Sucessfully deleted source with ID: " + source_id