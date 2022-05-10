from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import Field, dataclass, field
from email.policy import default
from uuid import UUID, uuid1
from typing import List, Tuple
import simpy
from process import Process
from material import Material
from state import State
from time_model import TimeModel
from collections.abc import Callable
import base
from resource import Resource

class Environment(ABC, simpy.Environment):

    def __init__(self, resource_process_registry, material_registry) -> None:
        super().__init__()
        self.resource_proces_registry : ResourceProcessRegistry = resource_process_registry
        self.material_registry : MaterialRegistry = material_registry

@dataclass
class MaterialRegistry(ABC):
    a: int

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