from typing import List
from fastapi import HTTPException

from prodsys.models import resource_data
from prodsys.adapters import adapter as prodsys_adapter
from app.dependencies import prodsys_backend


def get_all(
    project_id: str, adapter_id: str
) -> List[resource_data.RESOURCE_DATA_UNION]:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    return adapter.resource_data


def get_production_resources(
    project_id: str, adapter_id: str
) -> List[resource_data.ProductionResourceData]:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    return prodsys_adapter.get_machines(adapter)


def get_transport_resources(
    project_id: str, adapter_id: str
) -> List[resource_data.TransportResourceData]:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    return prodsys_adapter.get_transport_resources(adapter)


def get(
    project_id: str, adapter_id: str, resource_id: str
) -> resource_data.RESOURCE_DATA_UNION:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for resource in adapter.resource_data:
        if resource.ID == resource_id:
            return resource
    raise HTTPException(404, f"Resource with ID {resource_id} not found.")


def add(
    project_id: str, adapter_id: str, resource: resource_data.RESOURCE_DATA_UNION
) -> resource_data.RESOURCE_DATA_UNION:
    try:
        if get(project_id, adapter_id, resource.ID):
            raise HTTPException(
                404,
                f"Resource with ID {resource.ID} already exists. Try updating instead.",
            )
    except HTTPException:
        pass
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    adapter.resource_data.append(resource)
    prodsys_backend.update_adapter(project_id, adapter_id, adapter)
    return resource


def update(
    project_id: str,
    adapter_id: str,
    resource_id: str,
    resource: resource_data.RESOURCE_DATA_UNION,
) -> resource_data.RESOURCE_DATA_UNION:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for idx, existing_resource in enumerate(adapter.resource_data):
        if existing_resource.ID == resource_id:
            adapter.resource_data[idx] = resource
            prodsys_backend.update_adapter(project_id, adapter_id, adapter)
            return resource
    raise HTTPException(404, f"Resource with ID {resource_id} not found.")


def delete(project_id: str, adapter_id: str, resource_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for idx, resource in enumerate(adapter.resource_data):
        if resource.ID == resource_id:
            adapter.resource_data.pop(idx)
            prodsys_backend.update_adapter(project_id, adapter_id, adapter)
            return
    raise HTTPException(404, f"Resource with ID {resource_id} not found.")
