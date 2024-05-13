from fastapi import HTTPException
from prodsys.models import processes_data
from app.dependencies import prodsys_backend


def get_all(project_id: str, adapter_id: str) -> processes_data.PROCESS_DATA_UNION:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    return adapter.process_data


def get(
    project_id: str, adapter_id: str, process_id: str
) -> processes_data.PROCESS_DATA_UNION:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for process in adapter.process_data:
        if process.ID == process_id:
            return process
    raise HTTPException(404, f"Process with ID {process_id} not found.")


def add(
    project_id: str, adapter_id: str, process: processes_data.PROCESS_DATA_UNION
) -> processes_data.PROCESS_DATA_UNION:
    try:
        if get(project_id, adapter_id, process.ID):
            raise HTTPException(
                404,
                f"Process with ID {process.ID} already exists. Try updating instead.",
            )
    except HTTPException:
        pass
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    adapter.process_data.append(process)
    prodsys_backend.update_adapter(project_id, adapter_id, adapter)
    return process


def update(
    project_id: str,
    adapter_id: str,
    process_id: str,
    process: processes_data.PROCESS_DATA_UNION,
) -> processes_data.PROCESS_DATA_UNION:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for idx, existing_process in enumerate(adapter.process_data):
        if existing_process.ID == process_id:
            adapter.process_data[idx] = process
            prodsys_backend.update_adapter(project_id, adapter_id, adapter)
            return process
    raise HTTPException(404, f"Process with ID {process_id} not found.")


def delete(project_id: str, adapter_id: str, process_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for idx, process in enumerate(adapter.process_data):
        if process.ID == process_id:
            adapter.process_data.pop(idx)
            prodsys_backend.update_adapter(project_id, adapter)
            return
    raise HTTPException(404, f"Process with ID {process_id} not found.")
