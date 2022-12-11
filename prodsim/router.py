from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import Field, dataclass, field
from random import random
from turtle import pos
from typing import List, Tuple
from uuid import UUID, uuid1

import numpy as np
import simpy

from . import base, process, resources, sink
from .factories import resource_factory


@dataclass
class Router(ABC):
    resource_process_registry: resource_factory.ResourceFactory
    sink_registry: sink.SinkFactory
    routing_heuristic: Callable[..., resources.Resourcex]

    @abstractmethod
    def get_next_resource(self, __process: process.Process) -> resources.Resourcex:
        pass

    def get_sink(self, _material_type: str) -> sink.Sink:
        possible_sinks = self.sink_registry.get_sinks_with_material_type(_material_type)
        return self.routing_heuristic(possible_sinks)


@dataclass
class SimpleRouter(Router):
    def get_next_resource(self, __process: process.Process) -> resources.Resourcex:
        possible_resources = self.resource_process_registry.get_resources_with_process(
            __process
        )
        return self.routing_heuristic(possible_resources)


@dataclass
class AvoidDeadlockRouter(Router):
    def get_next_resource(self, __process: process.Process) -> resources.Resourcex:
        possible_resources = self.resource_process_registry.get_resources_with_process(
            __process
        )
        for resource in possible_resources:
            for input_queue in resource.input_queues:
                if len(possible_resources) > 1 and len(input_queue.items) >= input_queue.capacity - 3:
                    possible_resources.remove(resource)
        
        return self.routing_heuristic(possible_resources)


def FIFO_router(possible_resources: List[resources.Resourcex]) -> resources.Resourcex:
    return possible_resources.pop(0)


def random_router(possible_resources: List[resources.Resourcex]) -> resources.Resourcex:
    possible_resources.sort(key=lambda x: x.ID)
    return np.random.choice(possible_resources)


def get_shortest_quueue_router(
    possible_resources: List[resources.Resourcex],
) -> resources.Resourcex:
    queue_list = []
    for resource in possible_resources:
        if resource.input_queues:
            for q in resource.input_queues:
                queue_list.append((q, resource))
    if queue_list:
        queue_list.sort(key=lambda x: len(x[0].items))
        min_length = len(queue_list[0][0].items)
        resource_list = [queue[1] for queue in queue_list if len(queue[0].items) <= min_length]
        return resource_list.pop(0)
    return random_router(possible_resources=possible_resources)


ROUTING_HEURISTIC = {
    "shortest_queue": get_shortest_quueue_router,
    "random": random_router,
    "FIFO": FIFO_router,
}

ROUTERS = {"SimpleRouter": SimpleRouter, "AvoidDeadlockRouter": AvoidDeadlockRouter}