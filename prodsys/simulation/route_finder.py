from __future__ import annotations

from typing import Dict, List, TYPE_CHECKING, Optional, Tuple, Union

import numpy as np

from pathfinding.core.graph import Graph, GraphNode
from pathfinding.finder.dijkstra import DijkstraFinder

if TYPE_CHECKING:
    from prodsys.simulation import request, process, resources
    from prodsys.simulation.product import Locatable


def find_route(request: request.TransportResquest, process: process.LinkTransportProcess, find_route_to_origin: bool=False) -> List[Locatable]:
    """
    Finds the route for a transportation request.

    Args:
        request (request.TransportResquest): The transportation request.
        process (process.LinkTransportProcess): The process to find the route for.
        find_route_to_origin (bool, optional): Indicates whether to find the route from current resource location to origin (True) or from origin to target of request (False). Defaults to False.

    Returns:
        List[Locatable]: The route as a list of locatable objects.
    """
    if request.route and not find_route_to_origin:
        return request.route
    route_finder = RouteFinder()
    route = route_finder.find_route(request=request, process=process, find_route_to_origin=find_route_to_origin)
    if route and not find_route_to_origin:
        request.set_route(route=route)
    return route

class RouteFinder:
    """
    Class representing a route finder for transportation requests in a graph.
    """

    def __init__(self):
        """
        Initializes two empty lists of nodes and node locations.
        """
        self.nodes: Dict[str, GraphNode] = {}
        self.node_locatables: Dict[Tuple[float,float], Locatable] = {}

    def find_route(self, request: request.TransportResquest, process: process.LinkTransportProcess, find_route_to_origin: bool=False) -> List[Locatable]:
        """
        The general function which includes all sub functions to find the shortest route for a TransportRequest.

        Args:
            request (TransportResquest): The transportation request.
            process (LinkTransportProcess): The process to find the route for.
            find_route_to_origin (bool): Indicates whether to find the route from current resource location to origin (True) or from origin to target of request (False).

        Returns:
            List[Locatable]: The route as a list of locatable objects.
        """
        edges = self.process_links_to_graph_edges(links=process.links)
        # TODO: also add functionality to make directional edges for conveyors, where backwards routing is not possibly. 
        # For this feature is it necessary, that the location of the conveyor does not change after a transport.
        graph = Graph(edges=edges, bi_directional=True)
        origin, target = self.get_route_origin_and_target(request=request, route_to_origin=find_route_to_origin)
        if not origin or not target:
            return []
        graph_node_path = self.find_graphnode_path(origin, target, graph)
        if not graph_node_path:
            return []
        route = self.convert_node_path_to_locatable_route(graph_node_path=graph_node_path, links=process.links)

        return route

    def process_links_to_graph_edges(self, links: List[List[Locatable]]) -> List[Tuple[GraphNode, GraphNode, int]]:
        """
        Processes the given links to create (Graph)-edges for the graph.

        Args:
            request (TransportResquest): The transportation request.
            given_links_list: The given links list.

        Returns:
            List[Tuple[Graphnode, Graphnode, int]]: The edges as a list of tuples (with a start_node, end_node and related costs).
        """
        pathfinder_edges = []

        for link in links:
            cost = self.calculate_cost(link[0].get_location(), link[1].get_location())
            origin_graph_node, target_graph_node = self.get_graph_nodes_for_link(link)
            edge = (origin_graph_node, target_graph_node, cost)
            pathfinder_edges.append(edge)

        return pathfinder_edges
    
    def get_graph_nodes_for_link(self, link: List[Locatable]) -> Tuple[GraphNode, GraphNode]:
        """
        Creates a list of links and edges.

        Args:
            link (list): A list of nodes.
            link_edge (list): A list to store the link edges.
            graphnode_edge (list): A list to store the graph node edges.

        Returns:
            Tuple[GraphNode, GraphNode]: A tuple containing the origin and target nodes for a link.
        """
        graph_nodes = []
        for locatable in link:
            graph_node = self.get_graph_node_for_locatable(locatable)
            graph_nodes.append(graph_node)
        return tuple(graph_nodes)
    

    def get_existing_graph_node_for_locatable(self, locatable: Locatable) -> Optional[GraphNode]:
        """
        Gets an existing graph node for a Locatable.

        Args:
            locatable (Locatable): The locatable object.

        Returns:
            Optional[GraphNode, None]: The graph node or None.
        """
        if locatable.data.ID in self.nodes:
            return self.nodes[locatable.data.ID]
        return None
    
    def get_graph_node_for_locatable(self, locatable: Locatable) -> GraphNode:
        """
        Creates a graph node for a locatable.

        Args:
            locatable (Locatable): The locatable.

        Returns:
            GraphNode: The graph node.
        """
        existing_node = self.get_existing_graph_node_for_locatable(locatable)
        if existing_node:
            return existing_node
        new_graph_node = GraphNode(node_id=locatable.data.ID)
        self.nodes[locatable.data.ID] = new_graph_node
        self.node_locatables[tuple(locatable.get_location())] = locatable
        return new_graph_node
        

    def calculate_cost(self, node1: List[float], node2: List[float]) -> float:
        """
        Calculates the cost between two nodes based on the euclidean distance.

        Args:
            node1 (List[float]): The first node.
            node2 (List[float]): The second node.

        Returns:
            float: The cost.
        """
        # TODO: maybe use here the time model feature to weight the distance with the time it takes to travel it to optimize for fastest paths and not shortest paths
        return np.sqrt((node1[0] - node2[0])**2 + (node1[1] - node2[1])**2)

    def get_route_origin_and_target(self, request: request.TransportResquest, route_to_origin: bool) -> Tuple[Optional[GraphNode], Optional[GraphNode]]:
        """
        Converts the origin and target of the transport request to graph nodes.

        Args:
            request (TransportResquest): The transportation request.
            route_to_origin (bool): Indicates whether to find the route from current resource location to origin (True) or from origin to target of request (False).

        Returns:
            Tuple[Optional[GraphNode], Optional[GraphNode]]: A tuple containing the origin and target graph nodes for the transport request and the route_to_origin flag.
        """
        if route_to_origin:
            origin_locatable = self.get_location_of_transport_resource(request.resource)
            target_locatable = request.origin
        else:
            origin_locatable = request.origin
            target_locatable = request.target
        origin_graph_node = self.get_existing_graph_node_for_locatable(origin_locatable)
        target_graph_node = self.get_existing_graph_node_for_locatable(target_locatable)
        return origin_graph_node, target_graph_node
    
    def get_location_of_transport_resource(self, resource: resources.Resource) -> Locatable:
        """
        Gets the location of a resource.

        Args:
            resource (Resource): The resource.

        Returns:
            Locatable: The locatable object where the transport resource currently is.
        """
        resource_location = tuple(resource.get_location())
        if resource_location in self.node_locatables:
            return self.node_locatables[resource_location]
        raise ValueError(f"The current location for resource {resource.data.ID} could not be found. {resource.data.ID} is at location {resource.get_location()} that is not part of the links.")

    def find_graphnode_path(self, origin: GraphNode, target: GraphNode, graph: Graph) -> List[GraphNode]:
        """
        Finds the path between the origin and target graph nodes.

        Args:
            origin (GraphNode): The origin node.
            target (GraphNode): The target node.
            graph (Graph): The graph.

        Returns:
            The path as a list of graph nodes.
        """
        finder = DijkstraFinder()
        path, _ = finder.find_path(origin, target, graph)
        if path is None:
            return []
        return path

    def convert_node_path_to_locatable_route(self, graph_node_path: List[GraphNode], links: List[List[Locatable]]) -> List[Locatable]:
        """
        Converts the path of graph nodes to a route of Locatable objects.

        Args:
            graph_node_path (List[GraphNode]): The path as a list of graph nodes.
            links (List[List[Locatable]]): The given links list.

        Returns:
            List[Locatable]: The route as a list of locatable.
        """
        route = []
        seen_node_ids = []  # no node several times in the path

        for node in graph_node_path:
            for link in links:
                for locatable in link:
                    if node.node_id == locatable.data.ID and locatable.data.ID not in seen_node_ids:
                        route.append(locatable)
                        seen_node_ids.append(locatable.data.ID)
        return route
    