from typing import List, Dict


from fastapi import APIRouter

from prodsys.adapters import JsonProductionSystemAdapter

from app.dependencies import prodsys_backend

router = APIRouter(
    prefix="/projects/{project_id}/adapters",
    tags=["adapters"],
    responses={404: {"description": "Not found"}},
)

@router.get(
    "/",
    response_model=Dict[str, JsonProductionSystemAdapter]
)
async def get_adapters(project_id: str) -> List[JsonProductionSystemAdapter]:
    return prodsys_backend.get_adapters(project_id)

@router.post("/", response_model=JsonProductionSystemAdapter)
async def create_adapter(
    project_id: str,
    adapter: JsonProductionSystemAdapter,
) -> JsonProductionSystemAdapter:
    return prodsys_backend.create_adapter(project_id=project_id, adapter=adapter)


@router.get(
    "/{adapter_id}",
    response_model=JsonProductionSystemAdapter,
)
async def get_adapter(project_id: str, adapter_id: str) -> JsonProductionSystemAdapter:
    return prodsys_backend.get_adapter(project_id, adapter_id)


@router.put("/{adapter_id}")
async def update_adapter(
    project_id: str, adapter_id: str, adapter: JsonProductionSystemAdapter
) -> JsonProductionSystemAdapter:
    return prodsys_backend.update_adapter(project_id, adapter_id, adapter)


@router.delete("/{adapter_id}")
async def delete_adapter(project_id: str, adapter_id: str) -> str:
    prodsys_backend.delete_adapter(project_id, adapter_id)
    return f"Sucessfully deleted adapter with ID: {adapter_id}"