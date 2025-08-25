from __future__ import annotations

from typing import TYPE_CHECKING

from prodsys.models import port_data

if TYPE_CHECKING:
    from prodsys.simulation import request
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
            request.RequestType.PRIMITIVE_DEPENDENCY,
            request.RequestType.PROCESS_DEPENDENCY,
            request.RequestType.RESOURCE_DEPENDENCY,
        ):
            return None, None
        elif routed_request.request_type == request.RequestType.TRANSPORT:
            return self.handle_transport_interaction(routed_request)
        elif routed_request.request_type == request.RequestType.PRODUCTION:
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
        origin_output_ports = [
            q
            for q in routed_request.origin.ports
            if q.data.interface_type
            in [
                port_data.PortInterfaceType.OUTPUT,
                port_data.PortInterfaceType.INPUT_OUTPUT,
            ]
        ]
        origin_port = self.get_origin_port(origin_output_ports, routed_request)

        target_input_ports = [
            q
            for q in routed_request.target.ports
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
        target_output_ports = [
            q
            for q in routed_request.resource.ports
            if q.data.interface_type
            in [
                port_data.PortInterfaceType.OUTPUT,
                port_data.PortInterfaceType.INPUT_OUTPUT,
            ]
        ]
        target_port = self.get_target_port(target_output_ports, routed_request)
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
        origin_port = get_port_with_item(
            possible_ports, routed_request.requesting_item.data.ID
        )
        if origin_port is None:
            raise ValueError(
                f"No port found with item ID {routed_request.requesting_item.data.ID} in possible ports."
            )
        if (
            origin_port.data.port_type == port_data.PortType.STORE
        ):  # Ports can have multiple input / output locations -> select the most suitable one
            origin_port: port.Store
            origin_port = self.port_selection_heuristic(
                origin_port.store_ports, routed_request
            )
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
            target_port: port.Store
            target_port = self.port_selection_heuristic(
                target_port.store_ports, routed_request
            )
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

from prodsys.simulation import request
