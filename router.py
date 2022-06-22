from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import Field, dataclass, field
from email.policy import default
from uuid import UUID, uuid1
from typing import List, Tuple
import simpy

import base
import process
import material
import state
import time_model
from collections.abc import Callable
import resource
import random


@dataclass
class SimpleRouter:
    env: env.Environment
    resource_process_registry: resource.ResourceFactory
    routing_heuristic: Callable[List[resource], resource]

    """@abstractmethod
    def determine_next_processes(self, material: material.Material) -> List[Process]:
        pass"""

    def get_next_resource(self, _process: process.Process) -> resource.Resource:
        possible_resources = self.resource_process_registry.get_resources_with_process(_process)
        print(process.ID, [r.ID for r in possible_resources])

        return self.routing_heuristic(possible_resources)


def FIFO_router(possible_resources: List[resource.Resource]) -> resource.Resource:
    return possible_resources.pop()

def random_router(possible_resources: List[resource.Resource]) -> resource.Resource:
    return random.choice(possible_resources)