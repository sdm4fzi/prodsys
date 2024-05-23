from typing import List
from fastapi import HTTPException

from prodsys.models import source_data
from app.dependencies import prodsys_backend


def get_all(project_id: str, adapter_id: str) -> List[source_data.SourceData]:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    return adapter.source_data


def get(project_id: str, adapter_id: str, source_id: str) -> source_data.SourceData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for source in adapter.source_data:
        if source.ID == source_id:
            return source
    raise HTTPException(404, f"Source with ID {source_id} not found.")


def add(
    project_id: str, adapter_id: str, source: source_data.SourceData
) -> source_data.SourceData:
    try:
        if get(project_id, adapter_id, source.ID):
            raise HTTPException(
                404,
                f"Source with ID {source.ID} already exists. Try updating instead.",
            )
    except HTTPException:
        pass
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    adapter.source_data.append(source)
    prodsys_backend.update_adapter(project_id, adapter_id, adapter)
    return source


def update(
    project_id: str,
    adapter_id: str,
    source_id: str,
    source: source_data.SourceData,
) -> source_data.SourceData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for idx, existing_source in enumerate(adapter.source_data):
        if existing_source.ID == source_id:
            adapter.source_data[idx] = source
            prodsys_backend.update_adapter(project_id, adapter_id, adapter)
            return source
    raise HTTPException(404, f"Source with ID {source_id} not found.")


def delete(project_id: str, adapter_id: str, source_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for idx, source in enumerate(adapter.source_data):
        if source.ID == source_id:
            adapter.source_data.pop(idx)
            prodsys_backend.update_adapter(project_id, adapter_id, adapter)
            return
    raise HTTPException(404, f"Source with ID {source_id} not found.")
