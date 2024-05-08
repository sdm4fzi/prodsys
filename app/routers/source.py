from typing import List, Annotated


from fastapi import APIRouter, Body


from prodsys.models import source_data
from app.dao import source_dao

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
            "content": {"application/json": {"example": SOURCE_LIST_EXAMPLE}},
        },
        404: {"description": "No source data found."},
    },
)
async def get_sources(project_id: str, adapter_id: str):
    return source_dao.get_all(project_id, adapter_id)


@router.post(
    "/",
    response_model=source_data.SourceData,
    responses={
        200: {
            "description": "Successfully updated source data",
            "content": {"application/json": SOURCE_LIST_EXAMPLE},
        }
    },
)
async def create_sink(
    project_id: str,
    adapter_id: str,
    source: Annotated[
        source_data.SourceData,
        Body(example=source_data.SourceData.Config.schema_extra["example"]),
    ],
):
    return source_dao.add(project_id, adapter_id, source)


@router.get(
    "/{source_id}",
    response_model=source_data.SourceData,
    responses={
        200: {
            "description": "Successfulle returned source data.",
            "content": {"application/json": source_data.SourceData.Config.schema_extra},
        },
        404: {"description": "Sink not found."},
    },
)
async def get_source(project_id: str, adapter_id: str, source_id: str):
    return source_dao.get(project_id, adapter_id, source_id)


@router.put(
    "/{source_id}",
    response_model=source_data.SourceData,
    responses={
        200: {
            "description": "Successfully updated source data",
            "content": {"application/json": SOURCE_LIST_EXAMPLE},
        }
    },
)
async def update_source(
    project_id: str,
    adapter_id: str,
    source_id: str,
    source: Annotated[
        source_data.SourceData,
        Body(example=source_data.SourceData.Config.schema_extra["example"]),
    ],
):
    return source_dao.update(project_id, adapter_id, source_id, source)


@router.delete("/{source_id}", response_model=str)
async def delete_source(project_id: str, adapter_id: str, source_id: str):
    source_dao.delete(project_id, adapter_id, source_id)
    return f"Succesfully deleted source with id {source_id}"
