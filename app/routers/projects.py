from typing import List

from fastapi import APIRouter
from app.dependencies import Project, get_projects, get_project, database

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    responses={404: {"description": "Not found"}},
)

PROJECT_LIST_EXAMPLE = [Project.Config.schema_extra["example"]]


@router.get(
    "/",
    response_model=List[Project],
    responses={
        200: {
            "description": "Sucessfully returned projects",
            "content": {"application/json": {"example": PROJECT_LIST_EXAMPLE}},
        },
        404: {"description": "No projects found."},
    },
)
async def read_projects() -> List[Project]:
    return get_projects()


@router.put("/{project_id}")
async def create_project(
    project_id: str,
    project: Project,
) -> str:
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
