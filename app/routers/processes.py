from typing import List, Annotated


from fastapi import APIRouter, HTTPException, Body


from prodsys.data_structures import processes_data
from app.dependencies import get_adapter, get_process

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
    response_model=List[processes_data.ProcessData],
    responses={
        200: {
            "description": "Sucessfully returned processes",
            "content": {"application/json": {"example": PROCESSES_LIST_EXAMPLE}},
        },
    },
)
async def read_processes(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.process_data


@router.put(
    "/{process_id}",
)
async def create_process(
    project_id: str,
    adapter_id: str,
    process_id,
    process: Annotated[processes_data.ProcessData, Body(examples=PROCESSES_EXAMPLES)],
):
    if process.ID != process_id:
        raise HTTPException(404, "Process ID must not be changed")
    adapter = get_adapter(project_id, adapter_id)
    adapter.process_data.append(process)
    return "Sucessfully created process with ID: " + process.ID


@router.get(
    "/{process_id}",
    response_model=processes_data.ProcessData,
    responses={
        200: {
            "description": "Sucessfully returned process",
            "content": {"application/json": {"examples": PROCESSES_EXAMPLES}},
        }
    },
)
async def read_process(project_id: str, adapter_id: str, process_id: str):
    process = get_process(project_id, adapter_id, process_id)
    return process
