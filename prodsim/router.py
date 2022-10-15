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


@dataclass
class Router(ABC):
    resource_process_registry: resources.ResourceFactory
    sink_registry: sink.SinkFactory
    routing_heuristic: Callable[..., resources.Resource]

    @abstractmethod
    def get_next_resource(self, __process: process.Process) -> resources.Resource:
        pass

    def get_sink(self, _material_type: str) -> sink.Sink:
        possible_sinks = self.sink_registry.get_sinks_with_material_type(_material_type)
        return self.routing_heuristic(possible_sinks)


@dataclass
class SimpleRouter(Router):
    def get_next_resource(self, __process: process.Process) -> resources.Resource:
        possible_resources = self.resource_process_registry.get_resources_with_process(
            __process
        )
        return self.routing_heuristic(possible_resources)


@dataclass
class AvoidDeadlockRouter(Router):
    def get_next_resource(self, __process: process.Process) -> resources.Resource:
        possible_resources = self.resource_process_registry.get_resources_with_process(
            __process
        )
        if len(possible_resources) > 1:
            for resource in possible_resources:
                not_full = False
                for input_queue in resource.input_queues:
                    if not len(input_queue.items) == input_queue.capacity:
                        print(
                            f"resource {resource.ID}, input queue length {len(input_queue.items)}"
                        )
                        not_full = True
                        break
                    else:
                        print(f"resource {resource.ID} is full")
                        print(len(possible_resources))
                        possible_resources.remove(resource)
                        print(len(possible_resources))

        return self.routing_heuristic(possible_resources)


def FIFO_router(possible_resources: List[resources.Resource]) -> resources.Resource:
    return possible_resources.pop(0)


def random_router(possible_resources: List[resources.Resource]) -> resources.Resource:
    possible_resources.sort(key=lambda x: x.ID)
    return np.random.choice(possible_resources)


def get_shortest_quueue_router(
    possible_resources: List[resources.Resource],
) -> resources.Resource:
    queue_list = []
    for resource in possible_resources:
        if resource.input_queues:
            for q in resource.input_queues:
                queue_list.append((q, resource))
    if queue_list:
        queue_list.sort(key=lambda x: len(x[0].items))
        return queue_list.pop(0)[1]
    return FIFO_router(possible_resources=possible_resources)


ROUTING_HEURISTIC = {
    "shortest_queue": get_shortest_quueue_router,
    "random": random_router,
    "FIFO": FIFO_router,
}

ROUTERS = {"SimpleRouter": SimpleRouter, "AvoidDeadlockRouter": AvoidDeadlockRouter}
