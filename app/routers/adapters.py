from typing import List, Dict


from fastapi import APIRouter, Depends, HTTPException

import prodsys
from prodsys.data_structures import (
    time_model_data,
)


from app.dependencies import get_project, get_adapter

router = APIRouter(
    prefix="/projects/{project_id}/adapters",
    tags=["adapters"],
    responses={404: {"description": "Not found"}},
)

@router.get(
    "/",
    response_model=Dict[str, prodsys.adapters.JsonProductionSystemAdapter],
)
async def read_adapters(project_id: str):
    project = get_project(project_id)
    return project.adapters


@router.get(
    "/{adapter_id}",
    response_model=prodsys.adapters.JsonProductionSystemAdapter,
)
async def read_adapter(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter


@router.put("/{adapter_id}")
async def update_adapter(
    project_id: str, adapter_id: str, ada: prodsys.adapters.JsonProductionSystemAdapter
):
    project = get_project(project_id)
    project.adapters[adapter_id] = ada
    return "Sucessfully updated adapter with ID: " + adapter_id


@router.delete("/{adapter_id}")
async def delete_adapter(project_id: str, adapter_id: str):
    project = get_project(project_id)
    adapter = get_adapter(project_id, adapter_id)
    project.adapters.pop(adapter_id)
    return "Sucessfully deleted adapter with ID: " + adapter_id