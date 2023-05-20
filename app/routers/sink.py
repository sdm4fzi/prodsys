from typing import List, Annotated


from fastapi import APIRouter, HTTPException, Body


from prodsys.data_structures import (
    sink_data,
)
from app.dependencies import get_adapter, get_sink

# TIME_MODEL_EXAMPLES = {
#             "Sequential time model": time_model_data.SequentialTimeModelData.Config.schema_extra["example"],	
#             "Functional time model": time_model_data.FunctionTimeModelData.Config.schema_extra["example"],
#             "Manhattan Distance time model": time_model_data.ManhattanDistanceTimeModelData.Config.schema_extra["example"]
#         }

SINK_LIST_EXAMPLE = [sink_data.SinkData.Config.schema_extra["example"]["value"]]


router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/sinks",
    tags=["sinks"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/",
    response_model=List[sink_data.SinkData],
    responses={
        200: {
            "description": "Succesfully returned sink data",
            "content": {
                "application/json": {
                    "example": SINK_LIST_EXAMPLE
                }
            }
        },
        404: {"description": "No sink data found."}
    }
)
async def read_sinks(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.sink_data


@router.put("/{sink_id}")
async def create_sink(
    project_id: str,
    adapter_id: str,
    sink_id: str,
    sink: Annotated[sink_data.SinkData,
                    Body(example=sink_data.SinkData.Config.schema_extra["example"])]
):
    if sink.ID != sink_id:
        raise HTTPException(404, "Sink ID must not be changed")
    adapter = get_adapter(project_id, adapter_id)
    adapter.sink_data.append(sink)
    return "Sucessfully created sink with ID: " + sink.ID


@router.get(
    "/{sink_id}",
    response_model=sink_data.SinkData,
    responses={
        200: {
            "description": "Successfulle returned sink data.",
            "content": {
                "application/json": sink_data.SinkData.Config.schema_extra
            }
        },
        404: {"description": "Sink not found."}
    }
)
async def read_sink(project_id: str, adapter_id: str, sink_id: str):
    sink = get_sink(project_id, adapter_id, sink_id)
    return sink
