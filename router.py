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
from resource import Resource, ResourceFactory
from env import ResourceProcessRegistry, MaterialRegistry, Environment


@dataclass
class Router(ABC):
    env: Environment

    resource_process_registry: ResourceFactory
    material_registry: MaterialRegistry




    @abstractmethod
    def determine_next_processes(self, material: Material) -> List[Process]:
        pass

    @abstractmethod
    def get_next_possible_resources(self, process: Process) -> List[Resource]:
        pass

    @abstractmethod
    def wait_for_routing_decision():
        pass

    @abstractmethod
    def request_transport(self):
        pass
