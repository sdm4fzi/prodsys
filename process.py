from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple
from base import IDEntity
import simpy
from time_model import TimeModel
from uuid import uuid1, UUID


@dataclass
class Process(ABC, IDEntity):
    """
    Abstract process base class
    """
    description: str
    statistic: TimeModel


    @abstractmethod
    def get_process_time(self) -> float:
        pass

    @abstractmethod
    def set_statistic(self, statistic: TimeModel):
        pass

class ConcreteProcess(Process):

    def get_process_time(self) -> float:
        return self.statistic.get_next_time()

    def set_statistic(self, statistic: TimeModel):
        self.statistic = statistic


class ProcessModel(ABC):

    @abstractmethod
    def get_next_processes(self, process : Process) -> Tuple[Process]:
        pass

    @property
    @abstractmethod
    def process_model(self):
        pass


    def look_ahead(self, process : Process, look_ahead : int) -> List[Tuple[Process]]:
        pass





