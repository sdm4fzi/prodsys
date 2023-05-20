from typing import List, Annotated


from fastapi import APIRouter, HTTPException, Body


from prodsys.data_structures import (
    queue_data,
)
from app.dependencies import get_adapter, get_queue_data

QUEUE_LIST_EXAMPLE = [item["value"] for item in queue_data.QueueData.Config.schema_extra["examples"].values()]

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
async def read_queues(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.queue_data


@router.put(
    "/{queue_id}"
)
async def create_queue(
    project_id: str,
    adapter_id: str,
    queue_id: str,
    queue: Annotated[queue_data.QueueData, Body(examples=queue_data.QueueData.Config.schema_extra["examples"])],
):
    if queue.ID != queue_id:
        raise HTTPException(404, "Queue ID must not be changed")
    adapter = get_adapter(project_id, adapter_id)
    adapter.queue_data.append(queue)
    return "Sucessfully created queue with ID: " + queue.ID


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
async def read_queue(project_id: str, adapter_id: str, queue_id: str):
    queue = get_queue_data(project_id, adapter_id, queue_id)
    return queue