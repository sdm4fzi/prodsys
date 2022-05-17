from __future__ import annotations
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple

import simpy

import state
import process
import resource
import material

class Environment(simpy.Environment):
    material_registry: MaterialRegistry
    resource_process_registry: ResourceProcessRegistry

    def __init__(self) -> None:
        super().__init__()

    def add_material_registry(self, material_registry: MaterialRegistry) -> None:
        self.material_registry = material_registry

    def add_resource_process_registry(self, resource_process_registry: ResourceProcessRegistry) -> None:
        self.resource_process_registry = resource_process_registry

    def get_next_process(self, material: material.Material):
        pass

    def get_next_resource(self, resource: resource.Resource):
        pass


@dataclass
class MaterialRegistry(ABC):
    a: int


@dataclass
class ResourceProcessRegistry:
    resources: List[resource.Resource]
    processes: List[process.Process]
    process_statistics: List
    process_dict = dict()
    resource_dict = dict()

    def add_resource(self, resource: resource.Resource, processes: List[process.Process]) -> None:
        if resource in self.resource_dict:
            print("Resource is already in Registry!")
            return None
        self.resource_dict[resource] = processes
        for process in processes:
            if process not in self.process_dict.keys() and resource not in self.process_dict[process]:
                self.process_dict[process].append(resource)

    def get_possible_resources(self, process: process.Process) -> Tuple:
        pass

    def get_next_resource_process_time(self, resource: resource.Resource, process: process.Process) -> float:
        pass

    def get_next_process_time(self, process: process.Process) -> float:
        pass


@dataclass
class ManufacturingBOM(ABC):
    # materials: List[Material]
    processes: List[process.Process]
    connections: int

    @abstractmethod
    def get_material_for_process(self, process: process.Process) -> state.State:
        pass
