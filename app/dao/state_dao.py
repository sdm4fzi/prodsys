from typing import List
from fastapi import HTTPException
from prodsys.models import state_data
from app.dependencies import prodsys_backend


def get_all(project_id: str, adapter_id: str) -> List[state_data.STATE_DATA_UNION]:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    return adapter.state_data


def get(project_id: str, adapter_id: str, state_id: str) -> state_data.STATE_DATA_UNION:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for state in adapter.state_data:
        if state.ID == state_id:
            return state
    raise HTTPException(404, "State not found")


def add(project_id: str, adapter_id: str, state: state_data.STATE_DATA_UNION):
    try:
        if get(project_id, adapter_id, state.ID):
            raise HTTPException(
                404, f"State with ID {state.ID} already exists. Try updating instead."
            )
    except HTTPException:
        pass
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    adapter.state_data.append(state)
    prodsys_backend.update_adapter(project_id, adapter_id, adapter)
    return state


def update(
    project_id: str, adapter_id: str, state_id: str, state: state_data.STATE_DATA_UNION
):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for idx, existing_state in enumerate(adapter.state_data):
        if existing_state.ID == state_id:
            adapter.state_data[idx] = state
            prodsys_backend.update_adapter(project_id, adapter_id, adapter)
            return state
    raise HTTPException(404, f"State with ID {state_id} not found.")


def delete(project_id: str, adapter_id: str, state_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for idx, state in enumerate(adapter.state_data):
        if state.ID == state_id:
            adapter.state_data.pop(idx)
            prodsys_backend.update_adapter(project_id, adapter_id, adapter)
            return
    raise HTTPException(404, f"State with ID {state_id} not found.")
