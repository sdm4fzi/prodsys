from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import List, TYPE_CHECKING
import numpy as np

from prodsim.simulation import process
from prodsim.simulation import resources


if TYPE_CHECKING:
    from prodsim.simulation import resources, process, material, sink
    from prodsim.factories import resource_factory, sink_factory


class Router:
    def __init__(
        self,
        resource_factory: resource_factory.ResourceFactory,
        sink_factory: sink_factory.SinkFactory,
        routing_heuristic: Callable[..., resources.Resourcex],
    ):
        self.resource_factory: resource_factory.ResourceFactory = resource_factory
        self.sink_factory: sink_factory.SinkFactory = sink_factory
        self.routing_heuristic: Callable[..., material.Location] = routing_heuristic

    @abstractmethod
    def get_next_resource(self, __process: process.Process) -> resources.Resourcex:
        pass

    def get_sink(self, _material_type: str) -> sink.Sink:
        possible_sinks = self.sink_factory.get_sinks_with_material_type(_material_type)
        chosen_sink = self.routing_heuristic(possible_sinks)
        return chosen_sink  # type: ignore False


class SimpleRouter(Router):
    def get_next_resource(self, target_process: process.Process) -> resources.Resourcex:
        possible_resources = self.resource_factory.get_resources_with_process(
            target_process
        )
        return self.routing_heuristic(possible_resources)
    

def get_resource_capabilities(resource: resources.Resourcex) -> List[str]:
    capabilities = []
    for resource_process in resource.processes:
        if isinstance(resource_process, process.CapabilityProcess):
            capabilities.append(resource_process.process_data.capability)
        
    return capabilities


class CapabilityRouter(Router):
    def get_next_resource_per_ID(self, target_process: process.Process) -> resources.Resourcex:
        possible_resources = self.resource_factory.get_resources_with_process(
            target_process
        )
        return self.routing_heuristic(possible_resources)
    # TODO: maybe combine avoiddeadlockrouter and capabilityrouter -> seperate avoid deadlock logic and matching logic
    def get_next_resource(self, target_process: process.Process) -> resources.Resourcex:
        if isinstance(target_process, process.TransportProcess):
            return self.get_next_resource_per_ID(target_process)
        elif not isinstance(target_process, process.CapabilityProcess):
            raise ValueError(
                "CapabilityRouter can only be used with CapabilityProcess or TransportProcess"
            )
        possible_resources = []
        for resource in self.resource_factory.resources:
            resource_capabilities = get_resource_capabilities(resource)

            if target_process.process_data.capability in resource_capabilities:
                possible_resources.append(resource)

        return self.routing_heuristic(possible_resources)


class AvoidDeadlockRouter(Router):
    def get_next_resource(self, __process: process.Process) -> resources.Resourcex:
        possible_resources = self.resource_factory.get_resources_with_process(__process)
        for resource in possible_resources:
            if hasattr(resource, "input_queues"):
                for input_queue in resource.input_queues:
                    if (
                        len(possible_resources) > 1
                        and len(input_queue.items) >= input_queue.capacity - 3
                    ):
                        possible_resources.remove(resource)

        return self.routing_heuristic(possible_resources)


def FIFO_router(possible_resources: List[resources.Resourcex]) -> resources.Resourcex:
    return possible_resources.pop(0)


def random_router(possible_resources: List[resources.Resourcex]) -> resources.Resourcex:
    possible_resources.sort(key=lambda x: x.data.ID)
    return np.random.choice(possible_resources)  # type: ignore


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
        resource_list = [
            queue[1] for queue in queue_list if len(queue[0].items) <= min_length
        ]
        return resource_list.pop(0)
    return random_router(possible_resources=possible_resources)


ROUTING_HEURISTIC = {
    "shortest_queue": get_shortest_queue_router,
    "random": random_router,
    "FIFO": FIFO_router,
}

ROUTERS = {
    "SimpleRouter": SimpleRouter,
    "AvoidDeadlockRouter": AvoidDeadlockRouter,
    "CapabilityRouter": CapabilityRouter,
}
