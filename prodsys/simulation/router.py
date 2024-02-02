from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import List, TYPE_CHECKING, Optional, Generator

import logging
logger = logging.getLogger(__name__)

import numpy as np

from simpy import events

from prodsys.simulation import process
from prodsys.simulation import resources
from prodsys.simulation import request


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


    def route_request(self, processing_request: request.Request) -> Generator:
        """
        Routes a processing request to a resource and assigns the resource to the request.

        Args:
            request (request.Request): The request.

        Returns:
            Generator: A generator that yields when the request is routed.
        """
        possible_resources = self.get_possible_resources(processing_request)
        possible_resources_reached = []
        if not possible_resources:
            raise ValueError(f"No possible production resources found for request of product {processing_request.product.product_data.ID} and process {processing_request.process.process_data.ID}.")
        if not isinstance(processing_request, request.TransportResquest):
            for resource in possible_resources:
                if self.can_reach_resource(product=processing_request.product, resource=resource): 
                    possible_resources_reached.append(resource)
                else:
                    break
        else:
            possible_resources_reached = possible_resources
         
        if not possible_resources_reached:
            raise ValueError(f"No possible transport resources found for request of product {processing_request.product.product_data.ID} and process {processing_request.process.process_data.ID} to reach any destinations from resource {processing_request.product.current_location.data.ID}.")

        while True:
            free_resources = self.get_free_resources(possible_resources_reached)
            self.routing_heuristic(free_resources)
            # make timeout of 0 to make sure not two waiting requests are triggered at the same time and request the same resource
            yield processing_request.product.env.timeout(0)
            if free_resources:
                break
            logger.debug({"ID": processing_request.product.product_data.ID, "sim_time": processing_request.product.env.now, "event": f"Waiting for free resources."})
            yield events.AnyOf(
                processing_request.product.env,
                [resource.got_free for resource in possible_resources_reached],
            )
            logger.debug({"ID": processing_request.product.product_data.ID, "sim_time": processing_request.product.env.now, "event": f"Free resources available."})


        if not free_resources:
            raise ValueError("No free resources available, Error in Event handling of routing to resources.")
        routed_resource = free_resources[0]
        if isinstance(routed_resource, resources.ProductionResource):
            routed_resource.reserve_input_queues()
        processing_request.set_resource(routed_resource)
                
    def can_reach_resource(
        self, product: product.Product, resource: resources.Resource
    ) -> bool:
        """
        Checks if a product can reach a resource.

        Args:
            product (product.Product): The product.
            resource (resources.Resource): The resource.

        Returns:
            bool: True if the product can reach the resource, False otherwise.
        """
        # TODO: check, if this logic works with LinkTransportProcesses
        temporary_transport_request = request.TransportResquest(
            process=product.transport_process,
            product=product,
            origin=product.current_location,
            target = resource
        )
        possible_transport_resources = self.get_possible_resources(temporary_transport_request)
        if not possible_transport_resources:
            return False
        else:
            return True

    def get_free_resources(
        self, possible_resources: List[resources.Resource]
    ) -> List[resources.Resource]:
        """
        Abstract mehtod that returns a list of resources that have space in their input queues for the requested process.

        Args:
            requested_process (process.Process): The requested process.

        Returns:
            List[resources.Resource]: A list of resources that have space in their input queues for the requested process.
        """
        return [resource for resource in possible_resources if isinstance(resource, resources.TransportResource) or (isinstance(resource, resources.ProductionResource) and not any(q.full for q in resource.input_queues))]

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
        self, processing_request: request.Request
    ) -> List[resources.Resource]:
        """
        Returns a list of possible resources for a processing request.

        Args:
            processing_request (request.Request): The processing request.
        Returns:
            List[resources.Resource]: A list of possible resources for the process.
        """
        # TODO: maybe make result of function in dict and save it after instantiation. 
        possible_resources = []
        for resource in self.resource_factory.resources:
            for process in resource.processes:
                if process.matches_request(processing_request):
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
    np.random.shuffle(possible_resources)
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
