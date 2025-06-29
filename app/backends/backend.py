from typing import List, Protocol, Union

from app.models.project import Project
from prodsys.adapters import JsonProductionSystemAdapter
from prodsys.models.performance_data import Performance
from prodsys.optimization.optimizer import HyperParameters, Optimizer
from prodsys.util.post_processing import PostProcessor

class Backend(Protocol):

    def get_projects(self) -> List[Project]: ...

    def get_project(self, project_id: str) -> Project: ...

    def create_project(self, project: Project) -> Project: ...

    def update_project(self, project_id: str, project: Project) -> Project: ...

    def delete_project(self, project_id: str): ...

    def get_adapters(self, project_id: str) -> List[JsonProductionSystemAdapter]: ...

    def get_adapter(
        self, project_id: str, adapter_id: str
    ) -> JsonProductionSystemAdapter: ...

    def create_adapter(
        self, project_id: str, adapter: JsonProductionSystemAdapter
    ) -> JsonProductionSystemAdapter: ...

    def update_adapter(
        self, project_id: str, adapter_id: str, adapter: JsonProductionSystemAdapter
    ) -> JsonProductionSystemAdapter: ...

    def delete_adapter(self, project_id: str, adapter_id: str): ...

    def get_performance(self, project_id: str, adapter_id: str) -> Performance: ...

    def create_performance(
        self, project_id: str, adapter_id: str, performance: Performance
    ) -> Performance: ...

    def update_performance(
        self, project_id: str, adapter_id: str, performance: Performance
    ) -> Performance: ...

    def delete_performance(self, project_id: str, adapter_id: str): ...

    def get_post_processor(self, project_id: str, adapter_id: str) -> PostProcessor:
        ...

    def create_post_processor(self, project_id: str, adapter_id: str, post_processor: PostProcessor) -> PostProcessor:
        ...

    def update_post_processor(self, project_id: str, adapter_id: str, post_processor: PostProcessor) -> PostProcessor:
        ...

    def delete_post_processor(self, project_id: str, adapter_id: str):
        ...

    def save_optimizer_hyperparameters(
        self,
        project_id: str,
        adapter_id: str,
        optimizer_hyperparameters: Union[HyperParameters],
    ): ...

    def get_optimizer_hyperparameters(
        self, project_id: str, adapter_id: str
    ) -> HyperParameters: ...

    def save_optimizer(
        self, project_id: str, adapter_id: str, optimizer: Optimizer
    ) -> Optimizer: ...
    def get_optimizer(self, project_id: str, adapter_id: str) -> Optimizer: ...
