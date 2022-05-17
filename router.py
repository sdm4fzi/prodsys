from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import Field, dataclass, field
from email.policy import default
from uuid import UUID, uuid1
from typing import List, Tuple
import simpy
from process import Process
import material
import state
import time_model
from collections.abc import Callable
import resource


@dataclass
class Router(ABC):
    env: env.Environment

    resource_process_registry: resource.ResourceFactory
    material_registry: env.MaterialRegistry




    @abstractmethod
    def determine_next_processes(self, material: material.Material) -> List[Process]:
        pass

    @abstractmethod
    def get_next_possible_resources(self, process: Process) -> List[resource.Resource]:
        pass

    @abstractmethod
    def wait_for_routing_decision(self):
        pass

    @abstractmethod
    def request_transport(self):
        pass
