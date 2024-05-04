from typing import List, Annotated


from fastapi import APIRouter, HTTPException, Body


from prodsys.models import processes_data
from app.dao import process_dao

PROCESSES_EXAMPLES = {
    "Production process": processes_data.ProductionProcessData.Config.schema_extra[
        "example"
    ],
    "Transport process": processes_data.TransportProcessData.Config.schema_extra[
        "example"
    ],
    "Capability process": processes_data.CapabilityProcessData.Config.schema_extra[
        "example"
    ],
}

PROCESSES_LIST_EXAMPLE = [item["value"] for item in PROCESSES_EXAMPLES.values()]


router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/processes",
    tags=["processes"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/",
    response_model=List[processes_data.PROCESS_DATA_UNION],
    responses={
        200: {
            "description": "Sucessfully returned processes",
            "content": {"application/json": {"example": PROCESSES_LIST_EXAMPLE}},
        },
    },
)
async def get_processes(project_id: str, adapter_id: str):
    return process_dao.get_processes_from_backend(project_id, adapter_id)


@router.post(
    "/",
    response_model=List[processes_data.PROCESS_DATA_UNION],
    responses={
        200: {
            "description": "Sucessfully created process",
            "content": {"application/json": {"examples": PROCESSES_EXAMPLES}},
        }
    },
)
async def create_process(
    project_id: str,
    adapter_id: str,
    process: Annotated[
        processes_data.PROCESS_DATA_UNION, Body(examples=PROCESSES_LIST_EXAMPLE)
    ],
) -> processes_data.PROCESS_DATA_UNION:
    return process_dao.add_process_to_backend(project_id, adapter_id, process)


@router.get(
    "/{process_id}",
    response_model=processes_data.PROCESS_DATA_UNION,
    responses={
        200: {
            "description": "Sucessfully returned process",
            "content": {"application/json": {"examples": PROCESSES_EXAMPLES}},
        }
    },
)
async def get_process(project_id: str, adapter_id: str, process_id: str):
    return process_dao.get_process_from_backend(project_id, adapter_id, process_id)


@router.put(
    "/{process_id}",
    response_model=List[processes_data.PROCESS_DATA_UNION],
    responses={
        200: {
            "description": "Sucessfully updated process",
            "content": {"application/json": {"examples": PROCESSES_EXAMPLES}},
        }
    },
)
async def update_process(
    project_id: str,
    adapter_id: str,
    process_id,
    process: Annotated[
        processes_data.PROCESS_DATA_UNION, Body(examples=PROCESSES_LIST_EXAMPLE)
    ],
) -> processes_data.PROCESS_DATA_UNION:
    return process_dao.update_process_in_backend(
        project_id, adapter_id, process_id, process
    )


@router.delete("/{process_id}", response_model=str)
async def delete_process(project_id: str, adapter_id: str, process_id: str):
    process_dao.delete_process_from_backend(project_id, adapter_id, process_id)
    return f"Succesfully deleted process with ID {process_id}."
