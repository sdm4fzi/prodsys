from typing import List, Annotated


from fastapi import APIRouter, HTTPException, Body


from prodsys.models import (
    queue_data,
)
from app.dependencies import prodsys_backend, get_queue_from_backend

QUEUE_LIST_EXAMPLE = [item for item in queue_data.QueueData.Config.schema_extra["examples"]]

router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/queues",
    tags=["queues"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/",
    response_model=List[queue_data.QueueData],
    responses={
        200: {
            "description": "Sucessfully returned queues",
            "content": {
                "application/json": {
                    "example": QUEUE_LIST_EXAMPLE
        }
            },
        },
        404: {"description": "No queues found"},
    }
)
async def get_queues(project_id: str, adapter_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    return adapter.queue_data


@router.post(
    "/",
    response_model=queue_data.QueueData,
)
async def create_queue(
    project_id: str,
    adapter_id: str,
    queue: Annotated[queue_data.QueueData, Body(examples=queue_data.QueueData.Config.schema_extra["examples"])],
) -> queue_data.QueueData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    # TODO: make check if queue already exists, only add if not existing
    adapter.queue_data.append(queue)
    prodsys_backend.update_adapter(project_id, adapter)
    return queue


@router.get(
    "/{queue_id}",
    response_model=queue_data.QueueData,
    responses={
        200: {
            "description": "Sucessfully returned queue",
            "content": {
                "application/json": queue_data.QueueData.Config.schema_extra
            }
        },
        404: {"description": "Queue not found"},
    }
)
async def get_queue(project_id: str, adapter_id: str, queue_id: str):
    queue = get_queue_from_backend(project_id, adapter_id, queue_id)
    return queue

@router.put(
    "/{queue_id}",
    response_model=queue_data.QueueData,
)
async def update_queue(
    project_id: str,
    adapter_id: str,
    queue_id: str,
    queue: Annotated[queue_data.QueueData, Body(examples=QUEUE_LIST_EXAMPLE)],
) -> queue_data.QueueData:
    if queue.ID != queue_id:
        raise HTTPException(404, "Queue ID must not be changed")
    # TODO: update not working with this method, make also removal of old instance
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    adapter.queue_data.append(queue)
    return queue



@router.delete(
    "/{queue_id}",
    response_model=str
)
async def delete_queue(project_id: str, adapter_id: str, queue_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    queue = get_queue_from_backend(project_id, adapter_id, queue_id)
    adapter.queue_data.remove(queue)
    prodsys_backend.update_adapter(project_id, adapter)
    return "Sucessfully deleted queue with ID: " + queue_id