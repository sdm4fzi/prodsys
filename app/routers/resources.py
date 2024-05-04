from typing import List, Annotated


from fastapi import APIRouter, HTTPException, Body


from prodsys.models import resource_data
from app.dependencies import prodsys_backend, get_resource_from_backend

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
async def get_all_resources(project_id: str, adapter_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    return adapter.resource_data


@router.post(
    "/",
    response_model=resource_data.RESOURCE_DATA_UNION,
    responses={
        200: {
            "description": "Sucessfully created resource",
            "content": {"application/json": {"examples": RESOURCE_EXAMPLES}},
        }
    },
)
async def create_resource(
    project_id: str,
    adapter_id: str,
    resource: Annotated[
        resource_data.RESOURCE_DATA_UNION, Body(examples=RESOURCE_LIST_EXAMPLE)
    ],
) -> resource_data.RESOURCE_DATA_UNION:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    # TODO: only add resource if it does not exist, else raise error
    adapter.resource_data.append(resource)
    prodsys_backend.update_adapter(project_id, adapter)
    return resource


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
async def get_resource(project_id: str, adapter_id: str, resource_id: str):
    resource = get_resource_from_backend(project_id, adapter_id, resource_id)
    return resource


@router.put(
    "/{resource_id}",
)
async def update_resource(
    project_id: str,
    adapter_id: str,
    resource_id: str,
    resource: Annotated[
        resource_data.RESOURCE_DATA_UNION, Body(examples=RESOURCE_EXAMPLES)
    ],
) -> resource_data.RESOURCE_DATA_UNION:
    if resource.ID != resource_id:
        raise HTTPException(404, "Resource ID must not be changed")
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)#
    # TODO: make update of resource possible and update to backend
    adapter.resource_data.append(resource)
    return resource

@router.delete(
    "/{resource_id}",
)
async def delete_resource(project_id: str, adapter_id: str, resource_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    resource = get_resource_from_backend(project_id, adapter_id, resource_id)
    adapter.resource_data.remove(resource)
    prodsys_backend.update_adapter(project_id, adapter)
    return "Sucessfully deleted resource with ID: " + resource_id