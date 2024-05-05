from typing import List
from fastapi import HTTPException

from prodsys.models import time_model_data
from app.dependencies import prodsys_backend


def get_all(project_id: str, adapter_id: str) -> List[time_model_data.TIME_MODEL_DATA]:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    return adapter.time_model_data


def get(
    project_id: str, adapter_id: str, time_model_id: str
) -> time_model_data.TIME_MODEL_DATA:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for time_model in adapter.time_model_data:
        if time_model.ID == time_model_id:
            return time_model
    raise HTTPException(404, f"Time model with ID {time_model_id} not found.")


def add(
    project_id: str, adapter_id: str, time_model: time_model_data.TIME_MODEL_DATA
) -> time_model_data.TIME_MODEL_DATA:
    try:
        if get(project_id, adapter_id, time_model.ID):
            raise HTTPException(
                404,
                f"Time model with ID {time_model.ID} already exists. Try updating instead.",
            )
    except HTTPException:
        pass
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    adapter.time_model_data.append(time_model)
    prodsys_backend.update_adapter(project_id, adapter_id, adapter)
    return time_model


def update(
    project_id: str,
    adapter_id: str,
    time_model_id: str,
    time_model: time_model_data.TIME_MODEL_DATA,
) -> time_model_data.TIME_MODEL_DATA:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for idx, existing_time_model in enumerate(adapter.time_model_data):
        if existing_time_model.ID == time_model_id:
            adapter.time_model_data[idx] = time_model
            prodsys_backend.update_adapter(project_id, adapter_id, adapter)
            return time_model
    raise HTTPException(404, f"Time model with ID {time_model_id} not found.")


def delete(project_id: str, adapter_id: str, time_model_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for idx, time_model in enumerate(adapter.time_model_data):
        if time_model.ID == time_model_id:
            adapter.time_model_data.pop(idx)
            prodsys_backend.update_adapter(project_id, adapter_id, adapter)
            return
    raise HTTPException(404, f"Time model with ID {time_model_id} not found.")
