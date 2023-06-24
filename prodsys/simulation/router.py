from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import List, TYPE_CHECKING, Optional
import numpy as np

from simpy import events

from prodsys.simulation import process
from prodsys.simulation import resources


if TYPE_CHECKING:
    from prodsys.simulation import resources, process, product, sink
    from prodsys.factories import resource_factory, sink_factory
    from prodsys.control import routing_control_env


class Router:
    """
    Base class for all routers.

    Args:
        resource_factory (resource_factory.ResourceFactory): The resource factory of the production system.
        sink_factory (sink_factory.SinkFactory): The sink factory of the production system.
        routing_heuristic (Callable[[List[resources.Resource]], resources.Resource]): The routing heuristic to be used, needs to be a callable that takes a list of resources and returns a resource.
    """

    def __init__(
        self,
        resource_factory: resource_factory.ResourceFactory,
        sink_factory: sink_factory.SinkFactory,
        routing_heuristic: Callable[[List[resources.Resource]], resources.Resource],
    ):
        self.resource_factory: resource_factory.ResourceFactory = resource_factory
        self.sink_factory: sink_factory.SinkFactory = sink_factory
        self.routing_heuristic: Callable[[List[resources.Resource]]] = routing_heuristic

    @abstractmethod
    def get_free_resources(
        self, requested_process: process.Process
    ) -> List[resources.Resource]:
        """
        Abstract mehtod that returns a list of resources that have space in their input queues for the requested process.

        Args:
            requested_process (process.Process): The requested process.

        Returns:
            List[resources.Resource]: A list of resources that have space in their input queues for the requested process.
        """
        pass

    
    def set_next_production_resources(self, product_to_route: product.Product):
        """
        Sets the next resources for a product requring a production process. Resources that have full input queues are not considered.

        Args:
            product_to_route (product.Product): The product to route.
        """
        free_resources = self.get_free_resources(
            product_to_route.next_prodution_process
        )
        product_to_route.next_production_resources = free_resources
        if free_resources:
            self.routing_heuristic(free_resources)

    def set_next_transport_resources(self, product_to_route: product.Product):
        """
        Sets the next resources for a product requring a transport process.

        Args:
            product_to_route (product.Product): _description_
        """
        free_resources = self.get_free_resources(product_to_route.transport_process)
        product_to_route.next_transport_resources = free_resources
        if free_resources:
            self.routing_heuristic(free_resources)

    def get_sink(self, _product_type: str) -> sink.Sink:
        """
        Returns the sink for a product type.

        Args:
            _product_type (str): The product type.

        Returns:
            sink.Sink: The sink for the product type.
        """
        possible_sinks = self.sink_factory.get_sinks_with_product_type(_product_type)
        chosen_sink = np.random.choice(possible_sinks)
        return chosen_sink  # type: ignore False

    def get_possible_resources(
        self, target_process: process.Process
    ) -> List[resources.Resource]:
        """
        Returns a list of possible resources for a process.

        Args:
            target_process (process.Process): The process required by the product that needs to be routed.

        Returns:
            List[resources.Resource]: A list of possible resources for the process.
        """
        possible_resources = self.resource_factory.get_resources_with_process(
            target_process
        )
        return possible_resources


class SimpleRouter(Router):
    """
    Simple router that routes products based on the IDs of the processes.

    Args:
        resource_factory (resource_factory.ResourceFactory): The resource factory of the production system.
        sink_factory (sink_factory.SinkFactory): The sink factory of the production system.
        routing_heuristic (Callable[[List[resources.Resource]], resources.Resource]): The routing heuristic to be used, needs to be a callable that takes a list of resources and returns a resource.
    """

    def get_free_resources(
        self, requested_process: process.Process
    ) -> List[resources.Resource]:
        """
        Returns a list of resources that have space in their input queues for the requested process.

        Args:
            requested_process (process.Process): The requested process.

        Returns:
            List[resources.Resource]: A list of resources that have space in their input queues for the requested process.
        """
        possible_resources = self.resource_factory.get_resources_with_process(
            requested_process
        )
        left_resources = [resource for resource in possible_resources]

        for resource in possible_resources:
            if isinstance(resource, resources.ProductionResource):
                for input_queue in resource.input_queues:
                    if input_queue.full:
                        left_resources = [
                            r
                            for r in left_resources
                            if not r.data.ID == resource.data.ID
                        ]
                        break
        return left_resources



def get_resource_capabilities(resource: resources.Resource) -> List[str]:
    """
    Returns a list of capabilities of a resource.

    Args:
        resource (resources.Resource): The resource.

    Returns:
        List[str]: A list of capabilities of the resource.
    """
    capabilities = []
    for resource_process in resource.processes:
        if isinstance(resource_process, process.CapabilityProcess):
            capabilities.append(resource_process.process_data.capability)

    return capabilities


class CapabilityRouter(Router):
    """
    Router that routes products based on the capabilities of the processes.

    Args:
        resource_factory (resource_factory.ResourceFactory): The resource factory of the production system.
        sink_factory (sink_factory.SinkFactory): The sink factory of the production system.
        routing_heuristic (Callable[[List[resources.Resource]], resources.Resource]): The routing heuristic to be used, needs to be a callable that takes a list of resources and returns a resource.
    """

    def get_free_resources_per_ID(
        self, requested_process: process.Process
    ) -> List[resources.Resource]:
        """
        Returns a list of resources that have space in their input queues for the requested process.

        Args:
            requested_process (process.Process): The requested process.

        Returns:
            List[resources.Resource]: A list of resources that have space in their input queues for the requested process.
        """
        possible_resources = self.resource_factory.get_resources_with_process(
            requested_process
        )
        left_resources = [resource for resource in possible_resources]

        for resource in possible_resources:
            if isinstance(resource, resources.ProductionResource):
                for input_queue in resource.input_queues:
                    if input_queue.full:
                        left_resources = [
                            r
                            for r in left_resources
                            if not r.data.ID == resource.data.ID
                        ]
                        break
        return left_resources

    def get_free_resources(
        self, requested_process: process.Process
    ) -> List[resources.Resource]:
        """
        Returns a list of resources that have space in their input queues for the requested process.

        Args:
            requested_process (process.Process): The requested process.

        Raises:
            ValueError: If the requested process is not a CapabilityProcess.

        Returns:
            List[resources.Resource]: _description_
        """
        if isinstance(requested_process, process.TransportProcess):
            return self.get_free_resources_per_ID(requested_process)
        elif not isinstance(requested_process, process.CapabilityProcess):
            raise ValueError(
                "CapabilityRouter can only be used with CapabilityProcess or TransportProcess"
            )
        possible_resources = []
        for resource in self.resource_factory.resources:
            resource_capabilities = get_resource_capabilities(resource)
            if (
                requested_process.process_data.capability in resource_capabilities
            ) and not any(q.full for q in resource.input_queues):
                possible_resources.append(resource)
        return possible_resources


def FIFO_routing_heuristic(possible_resources: List[resources.Resource]):
    """
    Sorts the list by the FIFO principle.

    Args:
        possible_resources (List[resources.Resource]): A list of possible resources.
    """
    pass


def random_routing_heuristic(possible_resources: List[resources.Resource]):
    """
    Shuffles the list of possible resources.

    Args:
        possible_resources (List[resources.Resource]): A list of possible resources.
    """
    possible_resources.sort(key=lambda x: x.data.ID)
    np.random.shuffle(possible_resources)


def shortest_queue_routing_heuristic(
    possible_resources: List[resources.Resource],
):
    """
    Sorts the list of possible resources by the length of their input queues and returns the first resource.

    Args:
        possible_resources (List[resources.Resource]): A list of possible resources.
    """
    if any(not isinstance(resource, resources.ProductionResource) for resource in possible_resources):
        random_routing_heuristic(possible_resources)
        return
    possible_resources.sort(key=lambda x: sum([len(q.items) for q in x.input_queues]))


def agent_routing_heuristic(
    gym_env: routing_control_env.AbstractRoutingControlEnv,
    possible_resources: List[resources.Resource],
):
    """
    Sorts the list of possible resources by an reinforcement learning agent

    Args:
        gym_env (gym_env.ProductionRoutingEnv): Environment for the reinforcement learning agent.
        possible_resources (List[resources.Resource]): A list of possible resources.
    """
    if gym_env.interrupt_simulation_event.triggered:
        # Avoid that multiple requests trigger event multiple times -> delay them
        while possible_resources:
            possible_resources.pop()
        return
    gym_env.set_possible_resources(possible_resources)
    gym_env.interrupt_simulation_event.succeed()

ROUTING_HEURISTIC = {
    "shortest_queue": shortest_queue_routing_heuristic,
    "random": random_routing_heuristic,
    "FIFO": FIFO_routing_heuristic,
}
"""
A dictionary of available routing heuristics.
"""

ROUTERS = {
    "SimpleRouter": SimpleRouter,
    "CapabilityRouter": CapabilityRouter,
}
"""
A dictionary of available routers.
"""
