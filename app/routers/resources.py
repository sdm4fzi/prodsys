from typing import List, Annotated


from fastapi import APIRouter, Body


from prodsys.models import resource_data
from app.dao import resources_dao

RESOURCE_EXAMPLES = {
    "Production Resource": resource_data.ProductionResourceData.Config.schema_extra[
        "example"
    ],
    "Transport Resource": resource_data.TransportResourceData.Config.schema_extra[
        "example"
    ],
}

RESOURCE_LIST_EXAMPLE = [item["value"] for item in RESOURCE_EXAMPLES.values()]
PRODUCTION_RESOURCE_LIST_EXAMPLE = [
    resource_data.ProductionResourceData.Config.schema_extra["example"]["value"]
]
TRANSPORT_RESOURCE_LIST_EXAMPLE = [
    resource_data.TransportResourceData.Config.schema_extra["example"]["value"]
]


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
    return resources_dao.get_all(project_id, adapter_id)


@router.get(
    "/production_resources",
    response_model=List[resource_data.ProductionResourceData],
    responses={
        200: {
            "description": "Sucessfully returned production resources",
            "content": {
                "application/json": {"example": PRODUCTION_RESOURCE_LIST_EXAMPLE}
            },
        },
        404: {"description": "No resources found"},
    },
)
async def get_all_production_resources(project_id: str, adapter_id: str):
    return resources_dao.get_production_resources(project_id, adapter_id)


@router.get(
    "/transport_resources",
    response_model=List[resource_data.TransportResourceData],
    responses={
        200: {
            "description": "Sucessfully returned transport resources",
            "content": {
                "application/json": {"example": TRANSPORT_RESOURCE_LIST_EXAMPLE}
            },
        },
        404: {"description": "No resources found"},
    },
)
async def get_all_transport_resources(project_id: str, adapter_id: str):
    return resources_dao.get_transport_resources(project_id, adapter_id)


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
    return resources_dao.add(project_id, adapter_id, resource)


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
    return resources_dao.get(project_id, adapter_id, resource_id)


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
    return resources_dao.update(project_id, adapter_id, resource_id, resource)


@router.delete("/{resource_id}", response_model=str)
async def delete_resource(project_id: str, adapter_id: str, resource_id: str):
    resources_dao.delete(project_id, adapter_id, resource_id)
    return f"Succesfully deleted resource with ID {resource_id}"
