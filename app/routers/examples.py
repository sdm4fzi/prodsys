from typing import List


from fastapi import APIRouter, Depends, HTTPException


from prodsys.models import (
    time_model_data,
)

import prodsys
from app.dependencies import database, Project, evaluate


router = APIRouter(
    tags=["examples"],
    responses={404: {"description": "Not found"}},
)

@router.get("/load_example_project", response_model=str)
async def load_example_project() -> str:
    example_project = Project(ID="example_project")
    database.append(example_project)

    adapter_object = prodsys.adapters.JsonProductionSystemAdapter(ID="example_adapter_1")
    adapter_object.read_data("examples/basic_example/example_configuration.json")
    evaluate(adapter_object)
    example_project.adapters[adapter_object.ID] = adapter_object

    return "Sucessfully loaded example project"


@router.get("/load_optimization_example", response_model=str)
async def load_optimization_example_project() -> str:
    example_project = Project(ID="example_optimization_project")
    database.append(example_project)

    adapter_object = prodsys.adapters.JsonProductionSystemAdapter(ID="example_adapter_1")
    adapter_object.read_data(
        "examples/optimization_example/base_scenario.json",
        "examples/optimization_example/scenario.json",
    )
    example_project.adapters[adapter_object.ID] = adapter_object

    return "Sucessfully loaded optimization example project. Optimizations runs can be started now."
