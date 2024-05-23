from typing import List, Protocol

from app.models.project import Project
from prodsys.adapters import JsonProductionSystemAdapter
from prodsys.models.performance_data import Performance


class Backend(Protocol):

    def get_projects(self) -> List[Project]:
        ...

    def get_project(self, project_id: str) -> Project:
        ...

    def create_project(self, project: Project) -> Project:
        ...

    def update_project(self, project_id: str, project: Project) -> Project:
        ...

    def delete_project(self, project_id: str):
        ...

    
    def get_adapters(self, project_id: str) -> List[JsonProductionSystemAdapter]:
        ...

    def get_adapter(self, project_id: str, adapter_id: str) -> JsonProductionSystemAdapter:
        ...

    def create_adapter(self, project_id: str, adapter: JsonProductionSystemAdapter) -> JsonProductionSystemAdapter:
        ...

    def update_adapter(self, project_id: str, adapter_id: str, adapter: JsonProductionSystemAdapter) -> JsonProductionSystemAdapter:
        ...

    def delete_adapter(self, project_id: str, adapter_id: str):
        ...


    def get_performance(self, project_id: str, adapter_id: str) -> Performance:
        ...

    def create_performance(self, project_id: str, adapter_id: str, performance: Performance) -> Performance:
        ...

    def update_performance(self, project_id: str, adapter_id: str, performance: Performance) -> Performance:
        ...

    def delete_performance(self, project_id: str, adapter_id: str):
        ...

