from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Tuple, Type

import material
from base import IDEntity
from time_model import TimeModel, TimeModelFactory
from util import get_class_from_str


@dataclass
class Process(ABC, IDEntity):
    """
    Abstract process base class
    """
    time_model: TimeModel
    # raw_material: List[material.Material]
    # target_material: List[material.Material]

    @abstractmethod
    def get_process_time(self, *args) -> float:
        pass

    # def get_raw_material(self):
    #     return self.raw_material


class ProductionProcess(Process):

    def get_process_time(self) -> float:
        return self.time_model.get_next_time()

class TransportProcess(Process):

    def get_process_time(self, origin: List[float], target: List[float]) -> float:
        return self.time_model.get_next_time(originin=origin, target=target)


class ProcessModel(ABC):

    @abstractmethod
    def get_next_processes(self, process: Process) -> Tuple[Process]:
        pass

    @property
    @abstractmethod
    def process_model(self):
        pass

    def look_ahead(self, process: Process, look_ahead: int) -> List[Tuple[Process]]:
        pass


PROCESS_DICT: dict = {
    'ProductionProcesses': ProductionProcess,
    'TransportProcesses': TransportProcess,
}


@dataclass
class ProcessFactory:
    data: dict
    time_model_factory: TimeModelFactory
    processes: List[Process] = field(default_factory=list)

    def create_processes(self):
        processes = self.data['processes']
        for cls_name, items in processes.items():
            cls: Type[Process] = get_class_from_str(cls_name, PROCESS_DICT)
            for values in items.values():
                self.add_processes(cls, values)

    def add_processes(self, cls: Type[Process],  values: dict):
        time_model = self.time_model_factory.get_time_model(values['time_model_id'])
        self.processes.append(cls(ID=values['ID'], description=values['description'], time_model=time_model))

    def get_processes_in_order(self, IDs: List[str]) -> List[Process]:
        processes = []
        for ID in IDs:
            for _process in self.processes:
                if _process.ID == ID:
                    processes.append(_process)

        return processes


    def get_process(self, ID: str) -> Process:
        return [pr for pr in self.processes if pr.ID in ID].pop()




