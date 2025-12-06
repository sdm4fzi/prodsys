from __future__ import annotations

from typing import TYPE_CHECKING

# removed unused import P from pydantic.type_adapter

from prodsys.models import port_data
from prodsys.simulation import request

if TYPE_CHECKING:
    from prodsys.simulation import port


class InteractionHandler:

    def __init__(self):
        """
        Initializes the InteractionHandler.
        """
        # TODO: implement more sophisticated port selection heuristics (distance or number of items in the port based)
        self.port_selection_heuristic = random_port_selection_heuristic

        # TODO: precompute later the input and output ports of the resources, sinks and sources to be faster (use resource_factory, sink_factory, source_factory from router during init of InteractionHandler)
        self.input_ports_per_resource: dict[str, list[port.Queue]] = {}
        self.output_ports_per_resource: dict[str, list[port.Queue]] = {}

    def get_interaction_buffer(
        self, routed_request: request.Request
    ) -> port.Queue:
        if routed_request.request_type in (
            request.RequestType.ENTITY_DEPENDENCY,
            request.RequestType.PROCESS_DEPENDENCY,
            request.RequestType.RESOURCE_DEPENDENCY,
        ):
            return None
        elif routed_request.request_type == request.RequestType.TRANSPORT:
            return None
        elif routed_request.request_type in (request.RequestType.PRODUCTION, request.RequestType.PROCESS_MODEL):
            return self.handle_production_buffer(routed_request)
        else:
            raise ValueError(f"Unknown request type: {routed_request.request_type}")

    def handle_production_buffer(self, routed_request: request.Request) -> port.Queue:
        if not routed_request.resource.buffers:
            return None
        queue = self.port_selection_heuristic(routed_request.resource.buffers, routed_request)
        return queue

    def get_interaction_ports(
        self, routed_request: request.Request
    ) -> tuple[port.Queue, port.Queue]:
        """
        Returns the interaction ports for the given request.

        Args:
            request (request.Request): The request for which to get the interaction ports.

        Returns:
            tuple[store.Queue, store.Queue]: A tuple containing the input and output ports of the requesting item.
        """
        if routed_request.request_type in (
            request.RequestType.ENTITY_DEPENDENCY,
            request.RequestType.PROCESS_DEPENDENCY,
            request.RequestType.RESOURCE_DEPENDENCY,
        ):
            return None, None
        elif routed_request.request_type == request.RequestType.TRANSPORT:
            return self.handle_transport_interaction(routed_request)
        elif routed_request.request_type in (request.RequestType.PRODUCTION, request.RequestType.PROCESS_MODEL):
            return self.handle_production_interaction(routed_request)
        else:
            raise ValueError(f"Unknown request type: {routed_request.request_type}")

    def handle_transport_interaction(
        self, routed_request: request.Request
    ) -> tuple[port.Queue, port.Queue]:
        """
        Handles the interaction for transport requests.

        Args:
            routed_request (request.Request): The transport request.

        Returns:
            tuple[store.Queue, store.Queue]: A tuple containing the input and output ports of the requesting item.
        """
        # Get origin ports - handle Store objects that have store_ports instead of ports
        # For Node objects, we need to handle them specially since they don't have ports
        if hasattr(routed_request.origin, 'ports'):
            origin_ports = routed_request.origin.ports
        elif hasattr(routed_request.origin, 'store_ports'):
            origin_ports = routed_request.origin.store_ports
        else:
            # For Node objects or other locations without ports, return None to indicate direct location access
            origin_ports = None
            
        if origin_ports is None:
            # For Node objects or other locations without ports, use the location directly
            origin_port = routed_request.origin
        else:
            origin_output_ports = [
                q
                for q in origin_ports
                if q.data.interface_type
                in [
                    port_data.PortInterfaceType.OUTPUT,
                    port_data.PortInterfaceType.INPUT_OUTPUT,
                ]
            ]
            origin_port = self.get_origin_port(origin_output_ports, routed_request)

        # Get target ports - handle Store objects that have store_ports instead of ports
        if hasattr(routed_request.target, 'ports'):
            target_ports = routed_request.target.ports
        elif hasattr(routed_request.target, 'store_ports'):
            target_ports = routed_request.target.store_ports
        else:
            # For Node objects or other locations without ports, return None to indicate direct location access
            target_ports = None
            
        if target_ports is None:
            # For Node objects or other locations without ports, use the location directly
            target_port = routed_request.target
        else:
            target_input_ports = [
                q
                for q in target_ports
                if q.data.interface_type
                in [
                    port_data.PortInterfaceType.INPUT,
                    port_data.PortInterfaceType.INPUT_OUTPUT,
                ]
            ]
            # select target port that can accept the item
            target_port = self.get_target_port(target_input_ports, routed_request)

        return (origin_port, target_port)

    def handle_production_interaction(
        self, routed_request: request.Request
    ) -> tuple[port.Queue, port.Queue]:
        """
        Handles the interaction for production requests which input and output ports should be used at the resource.

        Args:
            routed_request (request.Request): The production request.

        Returns:
            tuple[store.Queue, store.Queue]: A tuple containing the input and output ports of the requesting item.
        """
        origin_input_ports = [
            q
            for q in routed_request.resource.ports
            if q.data.interface_type
            in [
                port_data.PortInterfaceType.INPUT,
                port_data.PortInterfaceType.INPUT_OUTPUT,
            ]
        ]
        origin_port = self.get_origin_port(origin_input_ports, routed_request)

        # Prefer dedicated OUTPUT ports for target; if none, use INPUT_OUTPUT but avoid the same
        # port selected for origin when possible to prevent returning to input.
        target_output_ports = [
            q
            for q in routed_request.resource.ports
            if q.data.interface_type
            in [
                port_data.PortInterfaceType.OUTPUT,
                port_data.PortInterfaceType.INPUT_OUTPUT,
            ]
        ]

        # Prioritize OUTPUT-only ports
        preferred_targets = [
            q for q in target_output_ports if q.data.interface_type == port_data.PortInterfaceType.OUTPUT
        ]
        fallback_targets = [
            q for q in target_output_ports if q.data.interface_type == port_data.PortInterfaceType.INPUT_OUTPUT and q is not origin_port
        ]
        filtered_targets = preferred_targets or fallback_targets or target_output_ports

        target_port = self.get_target_port(filtered_targets, routed_request)
        return (origin_port, target_port)

    def get_origin_port(
        self, possible_ports: list[port.Queue], routed_request: request.Request
    ) -> port.Queue:
        """
        Gets the most suitable origin port from the list of possible ports.

        Args:
            possible_ports (list[store.Queue]): List of possible origin ports.
            routed_request (request.Request): The routed request.

        Returns:
            store.Queue: The selected origin port.
        """
        # Distinguish primitives from products based on presence of product_info (primitives don't have it)
        if not hasattr(routed_request.requesting_item, 'product_info'):
            # Primitive: choose by heuristic
            origin_port = self.port_selection_heuristic(possible_ports, routed_request)
        else:
            # Product: find the concrete port that currently contains the item
            origin_port = get_port_with_item(
                possible_ports, routed_request.requesting_item.data.ID
            )
            if origin_port is None:
                raise ValueError(
                    f"No port found with item ID {routed_request.requesting_item.data.ID} in possible ports."
                )
        
        if origin_port is None:
            raise ValueError(
                f"No suitable port found for item ID {routed_request.requesting_item.data.ID} in possible ports."
            )
            
        if (
            origin_port.data.port_type == port_data.PortType.STORE
        ):  # Ports can have multiple input / output locations -> select the most suitable one
            if hasattr(origin_port, 'store_ports'):
                # This is a Store object with store_ports
                origin_port: port.Store
                origin_port = self.port_selection_heuristic(
                    origin_port.store_ports, routed_request
                )
            # If it's a StorePort, we don't need to do anything else
        return origin_port

    def get_target_port(
        self, possible_ports: list[port.Queue], routed_request: request.Request
    ) -> port.Queue:
        """
        Gets the most suitable target port from the list of possible ports.

        Args:
            possible_ports (list[store.Queue]): List of possible target ports.
            routed_request (request.Request): The routed request.

        Returns:
            store.Queue: The selected target port.
        """
        # TODO: consider here product_type compatibility logic
        target_port = self.port_selection_heuristic(possible_ports, routed_request)
        if target_port is None:
            raise ValueError(
                f"No suitable port found for item ID {routed_request.requesting_item.ID} in possible ports."
            )
        if target_port.data.port_type == port_data.PortType.STORE:
            if hasattr(target_port, 'store_ports'):
                # This is a Store object with store_ports
                target_port: port.Store
                target_port = self.port_selection_heuristic(
                    target_port.store_ports, routed_request
                )
            # If it's a StorePort, we don't need to do anything else
        return target_port


def get_port_with_item(ports: list[port.Queue], item_id: str) -> port.Queue:
    """
    Returns the port that contains the item with the given ID.

    Args:
        ports (list[store.Queue]): List of ports to search in.
        item_id (str): ID of the item to search for.

    Returns:
        store.Queue: The port that contains the item, or None if not found.
    """
    for port in ports:
        if item_id in port.items:
            return port
    return None


def random_port_selection_heuristic(
    possible_ports: list[port.Queue], routed_request: request.Request
) -> port.Queue:
    """
    Randomly selects a port from the given list of possible ports.

    Args:
        possible_ports (list[store.Queue]): List of possible ports to select from.

    Returns:
        store.Queue: A randomly selected port.
    """
    import random

    return random.choice(possible_ports)
