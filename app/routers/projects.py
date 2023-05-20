from typing import List


from fastapi import APIRouter, Depends, HTTPException


from prodsys.data_structures import (
    time_model_data,
)


from app.dependencies import Project, get_projects, get_project, database

# TODO: update the schema exaples


router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=List[Project])
async def read_projects() -> List[Project]:
    return get_projects()


@router.put("/{project_id}")
async def create_project(project: Project, ) -> str:
    database.append(project)
    return "Sucessfully created project with ID: " + project.ID

@router.get("/{project_id}", response_model=Project)
async def read_project(project_id: str) -> Project:
    return get_project(project_id)


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    project = get_project(project_id)
    database.remove(project)
    return "Sucessfully deleted project with ID: " + project_id