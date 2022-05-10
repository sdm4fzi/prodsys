from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import Field, dataclass
from uuid import UUID, uuid1
from typing import List, Tuple
import simpy
from process import Process
from material import Material
from state import State
from time_model import TimeModel
from collections.abc import Callable









@dataclass
class Resource(ABC, simpy.Resource):
    _id: UUID
    states: List[State]
    state : State
    processes: List[Process]
    parts_made: int = 0

    @abstractmethod
    def change_state(self, state: State) -> None:
        pass

    def add_state(self, state: State) -> None:
        self.states.append(state)

    @abstractmethod
    def process_state(self, state: State) -> None:
        pass

    @abstractmethod
    def reactivate(self):
        pass

    @abstractmethod
    def interrupt_state(self):
        pass

    def get_active_states(self) -> List[State]:
        return self.states

    @abstractmethod
    def set_active_state(self, state: State):
        self.state = state

@dataclass
class ResourceProcessRegistry:
    resources: List[Resource]
    processes: List[Process]
    process_statistics: List
    process_dict = dict()
    resource_dict = dict()

    def add_resource(self, resource: Resource, processes: List[Process]) -> None:
        if resource in self.resource_dict:
            print("Resource is already in Registry!")
            return None
        self.resource_dict[resource] = processes
        for process in processes:
            if process not in self.process_dict.keys() and resource not in self.process_dict[process]:
                self.process_dict[process].append(resource)

    def get_possible_resources(self, process: Process) -> Tuple:
        pass

    def get_next_resource_process_time(self, resource: Resource, process: Process) -> float:
        pass

    def get_next_process_time(self, process: Process) -> float:
        pass




@dataclass
class ManufacturingBOM(ABC):
    materials: List[Material]
    processes: List[Process]
    connections: int

    @abstractmethod
    def get_material_for_process(self, process: Process) -> State:
        pass


@dataclass
class MaterialRegistry(ABC):
    a: int


@dataclass
class Router(ABC):

    @abstractmethod
    def determine_next_processes(self, material: Material) -> List[Process]:
        pass

    @abstractmethod
    def get_next_possible_resources(self, process: Process):
        pass


