from typing import List
from urllib import response

from fastapi import APIRouter
from app.dependencies import (
    prodsys_backend,
)
from app.models.project import Project

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=List[Project])
async def get_all_projects() -> List[Project]:
    return prodsys_backend.get_projects()


@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: str) -> Project:
    return prodsys_backend.get_project(project_id)


@router.post("/", response_model=Project)
async def create_project(
    project: Project,
) -> Project:
    return prodsys_backend.create_project(project)


@router.put("/{project_id}", response_model=Project)
async def update_project(
    project_id: str,
    project: Project,
) -> Project:
    return prodsys_backend.update_project(project_id, project)


@router.delete("/{project_id}", response_model=str)
async def delete_project(project_id: str) -> str:
    prodsys_backend.delete_project(project_id)
    return "Sucessfully deleted project with ID: " + project_id
