from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import List, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from prodsim import resources, process
    from prodsim import sink
    from prodsim.factories import resource_factory, sink_factory



class Router:
    def __init__(self, resource_factory: resource_factory.ResourceFactory, sink_factory: sink_factory.SinkFactory, routing_heuristic: Callable[..., resources.Resourcex]):
        self.resource_factory: resource_factory.ResourceFactory = resource_factory
        self.sink_factory: sink_factory.SinkFactory = sink_factory
        self.routing_heuristic: Callable[..., resources.Resourcex] = routing_heuristic

    @abstractmethod
    def get_next_resource(self, __process: process.Process) -> resources.Resourcex:
        pass

    def get_sink(self, _material_type: str) -> sink.Sink:
        possible_sinks = self.sink_factory.get_sinks_with_material_type(_material_type)
        chosen_sink = self.routing_heuristic(possible_sinks)
        if isinstance(chosen_sink, sink.Sink):
            return chosen_sink
        else:
            raise TypeError("Routing heuristic did not return a sink")
        

class SimpleRouter(Router):
    def get_next_resource(self, target_process: process.Process) -> resources.Resourcex:
        possible_resources = self.resource_factory.get_resources_with_process(
            target_process
        )
        return self.routing_heuristic(possible_resources)


class AvoidDeadlockRouter(Router):
    def get_next_resource(self, __process: process.Process) -> resources.Resourcex:
        possible_resources = self.resource_factory.get_resources_with_process(
            __process
        )
        for resource in possible_resources:
            if not isinstance(resource, resources.ProductionResource):
                continue
            for input_queue in resource.input_queues:
                if len(possible_resources) > 1 and len(input_queue.items) >= input_queue.capacity - 3:
                    possible_resources.remove(resource)
        
        return self.routing_heuristic(possible_resources)


def FIFO_router(possible_resources: List[resources.Resourcex]) -> resources.Resourcex:
    return possible_resources.pop(0)


def random_router(possible_resources: List[resources.Resourcex]) -> resources.Resourcex:
    possible_resources.sort(key=lambda x: x.data.ID)
    return np.random.choice(possible_resources) # type: ignore

def get_shortest_queue_router(
    possible_resources: List[resources.Resourcex],
) -> resources.Resourcex:
    queue_list = []
    for resource in possible_resources:
        if not isinstance(resource, resources.ProductionResource):
            continue
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
    "shortest_queue": get_shortest_queue_router,
    "random": random_router,
    "FIFO": FIFO_router,
}

ROUTERS = {"SimpleRouter": SimpleRouter, "AvoidDeadlockRouter": AvoidDeadlockRouter}