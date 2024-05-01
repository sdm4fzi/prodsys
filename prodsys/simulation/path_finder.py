from __future__ import annotations

from typing import List, TYPE_CHECKING, Optional, Tuple, Union
from pathfinding.core.graph import Graph, GraphNode
from pathfinding.finder.dijkstra import DijkstraFinder

if TYPE_CHECKING:
    from prodsys.simulation import request, process, resources
    from prodsys.simulation.product import Location

class Pathfinder:
    """
    Class representing a path finder for transportation requests in a graph.
    """

    def __init__(self):
        """
        Initializes two empty lists of nodes and node locations.
        """
        # TODO: potentially use here dicts instead of list for faster access!
        self.nodes: List[GraphNode] = []
        self.node_locations: List[Location] = []

    def find_path(self, request: request.TransportResquest, process: process.LinkTransportProcess, find_path_to_origin: bool=False) -> List[Location]:
        """
        The general function which includes all sub functions to find the shortest path for a TransportRequest.

        Args:
            request (TransportResquest): The transportation request.
            process (LinkTransportProcess): The process to find the path for.
            find_path_to_origin (bool): Indicates whether to find the path from current resource location to origin (True) or from origin to target of request (False).

        Returns:
            List[Location]: The path as a list of locations.
        """
        edges = self.process_links_to_graph_edges(links=process.links)
        graph = Graph(edges=edges, bi_directional=True)
        origin, target = self.get_path_origin_and_target(request=request, path_to_origin=find_path_to_origin)
        if not origin or not target:
            print(request.resource.data.ID, request.origin.data.ID, request.target.data.ID)
            raise ValueError("Origin or target not found in graph, cannot find path. Routing should not happened for this request.")
        graph_node_path = self.find_graphnode_path(origin, target, graph)
        path = self.convert_node_path_to_location_path(graph_node_path=graph_node_path, links=process.links)
        path.reverse()

        return path

    def process_links_to_graph_edges(self, links: List[List[Location]]) -> List[Tuple[GraphNode, GraphNode, int]]:
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
    
    def get_graph_nodes_for_link(self, link: List[Location]) -> Tuple[GraphNode, GraphNode]:
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
        for location in link:
            graph_node = self.get_graph_node_for_location(location)
            graph_nodes.append(graph_node)
        return tuple(graph_nodes)
    

    def get_existing_graph_node_for_location(self, location: Location) -> Optional[GraphNode]:
        """
        Gets an existing graph node for a location.

        Args:
            location (Location): The location.

        Returns:
            Optional[GraphNode, None]: The graph node or None.
        """
        for existing_node in self.nodes:
            if existing_node.node_id == location.data.ID:
                return existing_node
        return None
    
    def get_graph_node_for_location(self, location: Location) -> GraphNode:
        """
        Creates a graph node for a location.

        Args:
            location (Location): The location.

        Returns:
            GraphNode: The graph node.
        """
        existing_node = self.get_existing_graph_node_for_location(location)
        if existing_node:
            return existing_node
        new_graph_node = GraphNode(node_id=location.data.ID)
        self.nodes.append(new_graph_node)
        self.node_locations.append(location)
        return new_graph_node
        

    def calculate_cost(self, node1, node2):
        """
        Calculates the cost between two nodes.

        Args:
            node1: The first node.
            node2: The second node.

        Returns:
            The cost between the two nodes.
        """
        return abs(node1[0] - node2[0]) + abs(node1[1] - node2[1])

    def get_path_origin_and_target(self, request: request.TransportResquest, path_to_origin: bool) -> Tuple[Optional[GraphNode], Optional[GraphNode]]:
        """
        Converts the origin and target of the transport request to graph nodes.

        Args:
            request (TransportResquest): The transportation request.
            path_to_origin (bool): Indicates whether to find the path from current resource location to origin (True) or from origin to target of request (False).

        Returns:
            Tuple[Optional[GraphNode], Optional[GraphNode]]: A tuple containing the origin and target graph nodes for the transport request and the path_to_origin flag.
        """
        if path_to_origin:
            origin_location = self.get_location_of_transport_resource(request.resource)
            target_location = request.origin
        else:
            origin_location = request.origin
            target_location = request.target
        origin_graph_node = self.get_existing_graph_node_for_location(origin_location)
        target_graph_node = self.get_existing_graph_node_for_location(target_location)
        return origin_graph_node, target_graph_node
    
    def get_location_of_transport_resource(self, resource: resources.Resource) -> Location:
        """
        Gets the location of a resource.

        Args:
            resource (Resource): The resource.

        Returns:
            Location: The location of the resource.
        """
        for location in self.node_locations:
            if location.get_location() == resource.get_location():
                return location
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
            return False
        return path

    def convert_node_path_to_location_path(self, graph_node_path: List[GraphNode], links: List[List[Location]]) -> List[Location]:
        """
        Converts the path of graph nodes to a path of links.

        Args:
            graph_node_path (List[GraphNode]): The path as a list of graph nodes.
            links (List[List[Location]]): The given links list.

        Returns:
            List[Location]: The path as a list of locations.
        """
        path = []
        seen_ids = []  # no node several times in the path

        for node in graph_node_path:
            for link in links:
                for location in link:
                    if node.node_id == location.data.ID and location.data.ID not in seen_ids:
                        path.append(location)
                        seen_ids.append(location.data.ID)
        return path
    