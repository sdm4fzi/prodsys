from typing import List, Annotated


from fastapi import APIRouter, HTTPException, Body


from prodsys.data_structures import (
    source_data
)
from app.dependencies import get_adapter, get_source

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
async def read_sources(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.source_data


@router.put("/{source_id}")
async def create_sink(
    project_id: str,
    adapter_id: str,
    source_id: str,
    source: Annotated[source_data.SourceData,
                    Body(example=source_data.SourceData.Config.schema_extra["example"])]
):
    if source.ID != source_id:
        raise HTTPException(404, "Source ID must not be changed")
    adapter = get_adapter(project_id, adapter_id)
    adapter.source_data.append(source)
    return "Sucessfully created source with ID: " + source.ID


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
async def read_source(project_id: str, adapter_id: str, source_id: str):
    source = get_source(project_id, adapter_id, source_id)
    return source
