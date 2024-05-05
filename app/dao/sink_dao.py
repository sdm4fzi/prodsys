from typing import List
from fastapi import HTTPException

from prodsys.models import sink_data
from app.dependencies import prodsys_backend


def get_all(project_id: str, adapter_id: str) -> List[sink_data.SinkData]:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    return adapter.sink_data


def get(project_id: str, adapter_id: str, sink_id: str) -> sink_data.SinkData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for sink in adapter.sink_data:
        if sink.ID == sink_id:
            return sink
    raise HTTPException(404, f"Sink with ID {sink_id} not found.")


def add(
    project_id: str, adapter_id: str, sink: sink_data.SinkData
) -> sink_data.SinkData:
    try:
        if get(project_id, adapter_id, sink.ID):
            raise HTTPException(
                404,
                f"Sink with ID {sink.ID} already exists. Try updating instead.",
            )
    except HTTPException:
        pass
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    adapter.sink_data.append(sink)
    prodsys_backend.update_adapter(project_id, adapter_id, adapter)
    return sink


def update(
    project_id: str,
    adapter_id: str,
    sink_id: str,
    sink: sink_data.SinkData,
) -> sink_data.SinkData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for idx, existing_sink in enumerate(adapter.sink_data):
        if existing_sink.ID == sink_id:
            adapter.sink_data[idx] = sink
            prodsys_backend.update_adapter(project_id, adapter_id, adapter)
            return sink
    raise HTTPException(404, f"Sink with ID {sink_id} not found.")


def delete(project_id: str, adapter_id: str, sink_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for idx, sink in enumerate(adapter.sink_data):
        if sink.ID == sink_id:
            adapter.sink_data.pop(idx)
            prodsys_backend.update_adapter(project_id, adapter_id, adapter)
            return
    raise HTTPException(404, f"Sink with ID {sink_id} not found.")
