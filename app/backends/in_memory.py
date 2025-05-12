import json
from typing import Dict, List, Union

from fastapi import HTTPException
from pydantic import TypeAdapter

from app.models.project import Project
from prodsys.adapters import JsonProductionSystemAdapter
from prodsys.models.performance_data import Performance
from prodsys.optimization.optimizer import HyperParameters, Optimizer
from prodsys.util.post_processing import PostProcessor


class InMemoryBackend:
    def __init__(self):
        self.database: Dict[str, Project] = {}

    def get_projects(self) -> List[Project]:
        return list(self.database.values())

    def get_project(self, project_id: str) -> Project:
        if not project_id in self.database:
            raise HTTPException(404, f"Project {project_id} not found")
        return self.database[project_id]

    def create_project(self, project: Project) -> Project:
        if project.ID in self.database:
            raise HTTPException(409, f"Project {project.ID} already exists. Try updating it with put.")
        self.database[project.ID] = project
        return project

    def update_project(self, project_id: str, project: Project) -> Project:
        self.delete_project(project_id)
        return self.create_project(project)

    def delete_project(self, project_id: str):
        if project_id not in self.database:
            raise HTTPException(404, f"Project {project_id} not found.")
        del self.database[project_id]

    def get_adapters(self, project_id: str) -> List[JsonProductionSystemAdapter]:
        project = self.get_project(project_id)
        return project.adapters

    def get_adapter(self, project_id: str, adapter_id: str) -> JsonProductionSystemAdapter:
        project = self.get_project(project_id)
        for adapter in project.adapters:
            if adapter.ID == adapter_id:
                return adapter
        raise HTTPException(404, f"Adapter {adapter_id} not found in project {project_id}")

    def create_adapter(self, project_id: str, adapter: JsonProductionSystemAdapter) -> JsonProductionSystemAdapter:
        project = self.get_project(project_id)
        if adapter.ID in [a.ID for a in project.adapters]:
            raise HTTPException(409, f"Adapter {adapter.ID} already exists in project {project_id}. Try updating it with put.")
        project.adapters.append(adapter)
        return adapter

    def update_adapter(self, project_id: str, adapter_id: str, adapter: JsonProductionSystemAdapter) -> JsonProductionSystemAdapter:
        self.delete_adapter(project_id, adapter_id)
        return self.create_adapter(project_id, adapter)

    def delete_adapter(self, project_id: str, adapter_id: str):
        project = self.get_project(project_id)
        for adapter_index, adapter in enumerate(project.adapters):
            if adapter.ID == adapter_id:
                del project.adapters[adapter_index]
                return
        self.delete_performance(project_id, adapter_id)
        raise HTTPException(404, f"Adapter {adapter_id} not found in project {project_id}")

    def get_performance(self, project_id: str, adapter_id: str) -> str:
        project = self.get_project(project_id)
        self.get_adapter(project_id, adapter_id)
        if adapter_id not in project.performances:
            raise HTTPException(404, f"Performance for adapter {adapter_id} not found in project {project_id}")
        return project.performances[adapter_id]  

    def create_performance(self, project_id: str, adapter_id: str, performance: Performance) -> str:
        project = self.get_project(project_id)
        self.get_adapter(project_id, adapter_id)
        if adapter_id in project.performances:
            raise HTTPException(409, f"Performance for adapter {adapter_id} already exists in project {project_id}. Try updating it with put.")
        project.performances[adapter_id] = performance
        return performance  

    def update_performance(self, project_id: str, adapter_id: str, performance: Performance) -> str:
        project = self.get_project(project_id)
        self.get_adapter(project_id, adapter_id)
        if adapter_id not in project.performances:
            raise HTTPException(404, f"Performance for adapter {adapter_id} not found in project {project_id}. Try creating it with post.")
        project.performances[adapter_id] = performance
        return performance

    def delete_performance(self, project_id: str, adapter_id: str):
        project = self.get_project(project_id)
        self.get_adapter(project_id, adapter_id)
        if adapter_id not in project.performances:
            raise HTTPException(404, f"Performance for adapter {adapter_id} not found in project {project_id}.")
        del project.performances[adapter_id]

    def save_optimizer_hyperparameters(self, project_id: str, adapter_id: str, optimizer_hyperparameters: Union[HyperParameters]):
        project = self.get_project(project_id)
        self.get_adapter(project_id, adapter_id)
        project.optimizer_hyperparameters[adapter_id] = optimizer_hyperparameters
        return optimizer_hyperparameters


    def get_optimizer_hyperparameters(
        self, project_id: str, adapter_id: str
    ) -> HyperParameters:
        project = self.get_project(project_id)
        self.get_adapter(project_id, adapter_id)
        if adapter_id not in project.optimizer_hyperparameters:
            raise HTTPException(
                404,
                f"Optimizer hyperparameters for adapter {adapter_id} not found in project {project_id}.",
            )
        return project.optimizer_hyperparameters[adapter_id]
    

    def save_optimizer(
        self, project_id: str, adapter_id: str, optimizer: Optimizer
    ):
        project = self.get_project(project_id)
        self.get_adapter(project_id, adapter_id)
        project.optimizer[adapter_id] = optimizer
        return optimizer
    

    def get_optimizer(
        self, project_id: str, adapter_id: str
    ) -> Optimizer:
        project = self.get_project(project_id)
        self.get_adapter(project_id, adapter_id)
        if adapter_id not in project.optimizer:
            raise HTTPException(
                404,
                f"Optimizer for adapter {adapter_id} not found in project {project_id}.",
            )
        return project.optimizer[adapter_id]