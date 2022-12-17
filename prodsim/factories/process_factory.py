from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from pydantic import BaseModel, parse_obj_as

from prodsim.factories import time_model_factory
from prodsim import process
from prodsim.data_structures import processes_data

if TYPE_CHECKING:
    from prodsim import adapter


class ProcessFactory(BaseModel):
    time_model_factory: time_model_factory.TimeModelFactory
    process_data: List[processes_data.PROCESS_DATA_UNION] = []
    processes: List[process.PROCESS_UNION] = []

    def create_processes_from_configuration_data(self, configuration_data: dict):
        for cls_name, items in configuration_data.items():
            # cls: Type[Process] = get_class_from_str(cls_name, PROCESS_DICT)
            for values in items.values():
                values.update({"type": cls_name})
                self.process_data.append(
                    parse_obj_as(processes_data.PROCESS_DATA_UNION, values)
                )
                self.add_processes(self.process_data[-1])

    def create_processes_from_adapter(self, adapter: adapter.Adapter):
        for process_data in adapter.process_data:
            self.add_processes(process_data)

    def add_processes(self, process_data: processes_data.PROCESS_DATA_UNION):
        values = {}
        time_model = self.time_model_factory.get_time_model(process_data.time_model_id)
        values.update({"time_model": time_model, "process_data": process_data})
        self.processes.append(parse_obj_as(process.PROCESS_UNION, values))

    def get_processes_in_order(self, IDs: List[str]) -> List[process.PROCESS_UNION]:
        processes = []
        for ID in IDs:
            for _process in self.processes:
                if _process.process_data.ID == ID:
                    processes.append(_process)

        return processes

    def get_process(self, ID: str) -> Optional[process.PROCESS_UNION]:
        pr = [pr for pr in self.processes if pr.process_data.ID in ID]
        if not pr:
            raise ValueError(f"Process with ID {ID} not found")
        return pr.pop()
