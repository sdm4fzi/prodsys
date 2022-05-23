from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Tuple

import material
from base import IDEntity
from time_model import TimeModel, TimeModelFactory


@dataclass
class Process(ABC, IDEntity):
    """
    Abstract process base class
    """
    time_model: TimeModel
    raw_material: List[material.Material]
    target_material: List[material.Material]

    @abstractmethod
    def get_process_time(self) -> float:
        pass

    def get_raw_material(self):
        return self.raw_material


class ConcreteProcess(Process):

    def get_process_time(self) -> float:
        return self.time_model.get_next_time()


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


@dataclass
class ProcessFactory:
    data: dict
    time_model_factory: TimeModelFactory
    processes: List[Process] = field(default_factory=list)

    def create_processes(self):
        processes = self.data['processes']
        for values in processes.values():
            self.add_processes(values)

    def add_processes(self, values: dict):
        time_model = self.time_model_factory.get_time_model(values['time_model_id'])
        self.processes.append(ConcreteProcess(time_model=time_model, ID=values['ID'], description=values['description']))

    def get_processes(self, IDs: List[str]) -> List[Process]:
        return [pr for pr in self.processes if pr.ID in IDs]





