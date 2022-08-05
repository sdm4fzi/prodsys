from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import Field, dataclass, field
from email.policy import default
from turtle import pos
from uuid import UUID, uuid1
from typing import List, Tuple
import simpy

import base
import process
from collections.abc import Callable
import resources
import numpy as np


@dataclass
class SimpleRouter:
    env: env.Environment
    resource_process_registry: resources.ResourceFactory
    routing_heuristic: Callable[..., resources.Resource]

    """@abstractmethod
    def determine_next_processes(self, material: material.Material) -> List[Process]:
        pass"""

    def get_next_resource(self, __process: process.Process) -> resources.Resource:
        possible_resources = self.resource_process_registry.get_resources_with_process(__process)
        return self.routing_heuristic(possible_resources)

def FIFO_router(possible_resources: List[resources.Resource]) -> resources.Resource:
    return possible_resources.pop()

def random_router(possible_resources: List[resources.Resource]) -> resources.Resource:
    return np.random.choice(possible_resources)