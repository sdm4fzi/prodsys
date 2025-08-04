from typing import List
from fastapi import HTTPException

from app.dependencies import prodsys_backend
from prodsys.models import port_data


def get_all(project_id: str, adapter_id: str) -> List[port_data.QueueData]:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    return adapter.port_data


def get(project_id: str, adapter_id: str, queue_id: str) -> port_data.QueueData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for queue in adapter.port_data:
        if queue.ID == queue_id:
            return queue
    raise HTTPException(404, f"Queue with ID {queue_id} not found.")


def add(
    project_id: str, adapter_id: str, queue: port_data.QueueData
) -> port_data.QueueData:
    try:
        if get(project_id, adapter_id, queue.ID):
            raise HTTPException(
                404,
                f"Queue with ID {queue.ID} already exists. Try updating instead.",
            )
    except HTTPException:
        pass
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    adapter.port_data.append(queue)
    prodsys_backend.update_adapter(project_id, adapter_id, adapter)
    return queue


def update(
    project_id: str, adapter_id: str, queue_id: str, queue: port_data.QueueData
) -> port_data.QueueData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for idx, existing_queue in enumerate(adapter.port_data):
        if existing_queue.ID == queue_id:
            adapter.port_data[idx] = queue
            prodsys_backend.update_adapter(project_id, adapter_id, adapter)
            return queue
    raise HTTPException(404, f"Queue with ID {queue_id} not found.")


def delete(project_id: str, adapter_id: str, queue_id: str) -> None:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for idx, existing_queue in enumerate(adapter.port_data):
        if existing_queue.ID == queue_id:
            adapter.port_data.pop(idx)
            prodsys_backend.update_adapter(project_id, adapter_id, adapter)
            return
    raise HTTPException(404, f"Queue with ID {queue_id} not found.")
