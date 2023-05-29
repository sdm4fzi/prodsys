from typing import List, Annotated


from fastapi import APIRouter, HTTPException, Body


from prodsys.models import resource_data
from app.dependencies import get_adapter, get_resource

# TIME_MODEL_EXAMPLES = {
#             "Sequential time model": time_model_data.SequentialTimeModelData.Config.schema_extra["example"],
#             "Functional time model": time_model_data.FunctionTimeModelData.Config.schema_extra["example"],
#             "Manhattan Distance time model": time_model_data.ManhattanDistanceTimeModelData.Config.schema_extra["example"]
#         }

# TIME_MODEL_LIST_EXAMPLE = [item["value"] for item in TIME_MODEL_EXAMPLES.values()]

RESOURCE_EXAMPLES = {
    "Production Resource": resource_data.ProductionResourceData.Config.schema_extra[
        "example"
    ],
    "Transport Resource": resource_data.TransportResourceData.Config.schema_extra[
        "example"
    ],
}

RESOURCE_LIST_EXAMPLE = [item["value"] for item in RESOURCE_EXAMPLES.values()]


router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/resources",
    tags=["resources"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/",
    response_model=List[resource_data.RESOURCE_DATA_UNION],
    responses={
        200: {
            "description": "Sucessfully returned resources",
            "content": {"application/json": {"example": RESOURCE_LIST_EXAMPLE}},
        },
        404: {"description": "No resources found"},
    },
)
async def read_resources(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.resource_data


@router.delete(
    "/{resource_id}",
)
async def delete_resource(project_id: str, adapter_id: str, resource_id: str):
    adapter = get_adapter(project_id, adapter_id)
    resource = get_resource(project_id, adapter_id, resource_id)
    adapter.resource_data.remove(resource)
    return "Sucessfully deleted resource with ID: " + resource_id


@router.get(
    "/{resource_id}",
    response_model=resource_data.RESOURCE_DATA_UNION,
    responses={
        200: {
            "description": "Sucessfully returned resource",
            "content": {"application/json": {"examples": RESOURCE_EXAMPLES}},
        },
        404: {"description": "Resource not found"},
    },
)
async def read_resource(project_id: str, adapter_id: str, resource_id: str):
    resource = get_resource(project_id, adapter_id, resource_id)
    return resource


@router.put(
    "/{resource_id}",
)
async def create_resource(
    project_id: str,
    adapter_id: str,
    resource_id: str,
    resource: Annotated[
        resource_data.RESOURCE_DATA_UNION, Body(examples=RESOURCE_EXAMPLES)
    ],
):
    if resource.ID != resource_id:
        raise HTTPException(404, "Resource ID must not be changed")
    adapter = get_adapter(project_id, adapter_id)
    adapter.resource_data.append(resource)
    return "Sucessfully updated resource with ID: " + resource_id
