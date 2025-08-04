from typing import List, Annotated


from fastapi import APIRouter, Body


from app.dao import queue_dao
from prodsys.models import (
    port_data,
)

QUEUE_LIST_EXAMPLE = [
    item for item in port_data.QueueData.model_config["json_schema_extra"]["examples"]
]

router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/queues",
    tags=["queues"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/",
    response_model=List[port_data.QueueData],
    responses={
        200: {
            "description": "Sucessfully returned queues",
            "content": {"application/json": {"example": QUEUE_LIST_EXAMPLE}},
        },
        404: {"description": "No queues found"},
    },
)
async def get_queues(project_id: str, adapter_id: str):
    return queue_dao.get_all(project_id, adapter_id)


@router.post(
    "/",
    response_model=port_data.QueueData,
)
async def create_queue(
    project_id: str,
    adapter_id: str,
    queue: Annotated[
        port_data.QueueData,
        Body(examples=port_data.QueueData.model_config["json_schema_extra"]["examples"]),
    ],
) -> port_data.QueueData:
    return queue_dao.add(project_id, adapter_id, queue)


@router.get(
    "/{queue_id}",
    response_model=port_data.QueueData,
    responses={
        200: {
            "description": "Sucessfully returned queue",
            "content": {"application/json": port_data.QueueData.model_config["json_schema_extra"]["examples"]},
        },
        404: {"description": "Queue not found"},
    },
)
async def get_queue(project_id: str, adapter_id: str, queue_id: str):
    return queue_dao.get(project_id, adapter_id, queue_id)


@router.put(
    "/{queue_id}",
    response_model=port_data.QueueData,
)
async def update_queue(
    project_id: str,
    adapter_id: str,
    queue_id: str,
    queue: Annotated[port_data.QueueData, Body(examples=QUEUE_LIST_EXAMPLE)],
) -> port_data.QueueData:
    return queue_dao.update(project_id, adapter_id, queue_id, queue)


@router.delete("/{queue_id}", response_model=str)
async def delete_queue(project_id: str, adapter_id: str, queue_id: str):
    queue_dao.delete(project_id, adapter_id, queue_id)
    return f"Succesfully deleted queue with ID {queue_id}"
