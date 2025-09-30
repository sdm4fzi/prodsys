from __future__ import annotations

from typing import TYPE_CHECKING
#import prodsys
from prodsys.models import port_data
from prodsys.simulation.port import Queue_per_product
if TYPE_CHECKING:
    from prodsys.simulation import request
    from prodsys.simulation import port
    from prodsys.simulation.port import StorePort
    
    

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
            request.RequestType.PRIMITIVE_FINISHED_DEPENDENCY,
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
        if isinstance(origin_output_ports[0].data, port_data.Queue_Per_Product_Data):
            origin_port = self.get_dedicated_origin_port(origin_output_ports, routed_request)
        else:        
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
        if isinstance(target_input_ports[0].data, port_data.Queue_Per_Product_Data):
            target_port = self.get_dedicated_target_port(target_input_ports, routed_request)
        else:        
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
        #INFO express API works with INPUT_OUTPUT Queues
       
        origin_input_ports = [
            q
            for q in routed_request.resource.ports
            if q.data.interface_type
            in [
                port_data.PortInterfaceType.INPUT,
                port_data.PortInterfaceType.INPUT_OUTPUT,
                ]
            ]

        if isinstance(origin_input_ports[0].data, port_data.Queue_Per_Product_Data):
            origin_port = self.get_dedicated_origin_port(origin_input_ports, routed_request)
        else:        
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
        if isinstance(target_output_ports[0].data, port_data.Queue_Per_Product_Data):
            target_port = self.get_dedicated_target_port(target_output_ports, routed_request)
        else:        
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
            store.Queue: The selected origin port."""
        origin_port = get_port_with_item(
            possible_ports, routed_request.requesting_item.data.ID
        )
        if origin_port is None:
            raise ValueError(
                f"No port found with item ID {routed_request.requesting_item.data.ID} in possible ports."
            )
        #FIXME: quick fix, gelöscht
        return origin_port
    def get_dedicated_origin_port(self,possible_ports: list[port.Queue_per_product],routed_request: request.Request
    ) -> port.Queue_per_product:
        
        for input_queue in possible_ports:
              
            if input_queue.data.product == routed_request.requesting_item.data.type:
                origin_queue = input_queue
        return origin_queue

    def get_dedicated_target_port(self,possible_ports: list[port.Queue_per_product],routed_request: request.Request
    ) -> port.Queue_per_product:
        #TODO output_queue name is misleading: change
        
        for output_queue in possible_ports:
            
                if output_queue.data.product == routed_request.requesting_item.data.type:
                    
                    target_queue = output_queue 
        return target_queue
        
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
        #FIXME: quick fix, gelöscht
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
        if hasattr(port, "store" ):
            print(port.store.items)
            if item_id in port.store.items:
                return port
        else:
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
