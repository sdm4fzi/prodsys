from __future__ import annotations

from typing import Dict, List, TYPE_CHECKING, Optional, Tuple, Union

import numpy as np

from pathfinding.core.graph import Graph, GraphNode
from pathfinding.finder.dijkstra import DijkstraFinder
# TODO: consider using a star for finding faster routes
from pathfinding.finder.a_star import AStarFinder

if TYPE_CHECKING:
    from prodsys.simulation import request, process, resources
    from prodsys.simulation.locatable import Locatable


def find_route(
    request: request.Request,
    process: process.LinkTransportProcess,
    find_route_to_origin: bool = False,
) -> List[Locatable]:
    """
    Finds the route for a transportation request.

    Args:
        request (request.Request): The transportation request.
        process (process.LinkTransportProcess): The process to find the route for.
        find_route_to_origin (bool, optional): Indicates whether to find the route from current resource location to origin (True) or from origin to target of request (False). Defaults to False. This also indicates whether material is transported or not.

    Returns:
        List[Locatable]: The route as a list of locatable objects.
    """
    if request.route and not find_route_to_origin:
        return request.route
    route_finder = RouteFinder()
    route = route_finder.find_route(
        request=request, process=process, find_route_to_origin=find_route_to_origin
    )
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

    def find_route(
        self,
        request: request.Request,
        process: process.LinkTransportProcess,
        find_route_to_origin: bool = False,
    ) -> List[Locatable]:
        """
        The general function which includes all sub functions to find the shortest route for a TransportRequest.

        Args:
            request (Request): The transportation request.
            process (LinkTransportProcess): The process to find the route for.
            find_route_to_origin (bool): Indicates whether to find the route from current resource location to origin (True) or from origin to target of request (False).

        Returns:
            List[Locatable]: The route as a list of locatable objects.
        """
        origin, target = self.get_route_origin_and_target_locatables(
            request=request, route_to_origin=find_route_to_origin
        )
        edges = self.process_links_to_graph_edges(
            links=process.links,
            origin=origin,
            target=target,
            empty_transport=find_route_to_origin,
        )  # finding route to origin is always an empty transport, since material is picked up at the origin

        # TODO: also add functionality to make directional edges for conveyors, where backwards routing is not possibly.
        origin_node, target_node = self.get_route_origin_and_target(
            request=request, route_to_origin=find_route_to_origin
        )

        graph = Graph(edges=edges, bi_directional=True)
        if not origin_node or not target_node:
            return []
        graph_node_path = self.find_graphnode_path(origin_node, target_node, graph)
        if not graph_node_path:
            return []
        route = self.convert_node_path_to_locatable_route(
            graph_node_path=graph_node_path, links=process.links
        )

        if hasattr(origin, 'can_move') and origin.can_move:
            route = route[1:]
        return route

    def process_links_to_graph_edges(
        self,
        links: List[List[Locatable]],
        origin: Locatable,
        target: Locatable,
        empty_transport: bool,
    ) -> List[Tuple[GraphNode, GraphNode, int]]:
        """
        Processes the given links to create (Graph)-edges for the graph.

        Args:
            links (List[List[Locatable]]): The links as a list of lists of locatable objects.
            origin (Locatable): The origin locatable object.
            target (Locatable): The target locatable object.
            empty_transport (bool): Indicates whether the transport is empty or an entity is transported.

        Returns:
            List[Tuple[Graphnode, Graphnode, int]]: The edges as a list of tuples (with a start_node, end_node and related costs).
        """
        # TODO: make the imports at top or bottom of file
        from prodsys.simulation.port import Store
        from prodsys.simulation.resources import Resource

        pathfinder_edges = []

        if hasattr(origin, 'can_move') and origin.can_move:
            # this is necessary since a transport resource can be initialized with a random location, so a link is needed for the first drive
            origin_location = origin.get_location()
            closest_locatable = None
            for link in links:
                for locatable in link:
                    if closest_locatable is None:
                        closest_locatable = locatable
                    if self.calculate_cost(
                        origin_location, locatable.get_location()
                    ) < self.calculate_cost(
                        origin_location, closest_locatable.get_location()
                    ):
                        closest_locatable = locatable
            links.append([origin, closest_locatable])

        for link in links:
            link_origin = link[0]
            link_target = link[1]
            if (
                not isinstance(link_origin, (Store)) or (isinstance(link_origin, Resource) and not (hasattr(link_origin, 'can_move') and link_origin.can_move)) 
                or not link_origin == origin
            ):
                origin_location = link_origin.get_location()
            elif empty_transport:
                origin_location = link_origin.get_location(interaction="input")
            elif not empty_transport:
                origin_location = link_origin.get_location(interaction="output")

            if (
                not isinstance(link_target, (Store)) or (isinstance(link_target, Resource) and not (hasattr(link_target, 'can_move') and link_target.can_move))
                or not link_target == target
            ):
                target_location = link_target.get_location()
            elif empty_transport:
                target_location = link_target.get_location(interaction="output")
            elif not empty_transport:
                target_location = link_target.get_location(interaction="input")

            edge = self.get_graph_edge(
                link_origin,
                link_target,
                origin_location=origin_location,
                target_location=target_location,
            )
            pathfinder_edges.append(edge)

        return pathfinder_edges

    def get_graph_edge(
        self,
        origin: Locatable,
        target: Locatable,
        origin_location: list[float],
        target_location: list[float],
    ) -> Tuple[GraphNode, GraphNode, int]:
        """
        Creates a graph edge for a link.

        Args:
            link (List[Locatable]): The link as a list of two locatable objects.
            origin_location (List[float]): The origin location.
            target_location (List[float]): The target location.

        Returns:
            Tuple[GraphNode, GraphNode, int]: A tuple containing the origin and target nodes for a link and the cost.
        """
        cost = self.calculate_cost(origin_location, target_location)
        origin_graph_node = self.get_graph_node_for_locatable(origin, origin_location)
        target_graph_node = self.get_graph_node_for_locatable(target, target_location)
        return origin_graph_node, target_graph_node, cost

    def get_existing_graph_node_for_locatable(
        self, locatable: Locatable
    ) -> Optional[GraphNode]:
        """
        Gets an existing graph node for a Locatable.

        Args:
            locatable (Locatable): The locatable object to get the graph node for.

        Returns:
            Optional[GraphNode, None]: The graph node or None.
        """
        if locatable.data.ID in self.nodes:
            return self.nodes[locatable.data.ID]
        return None

    def get_graph_node_for_locatable(
        self, locatable: Locatable, location: list[float]
    ) -> GraphNode:
        """
        Creates a graph node for a locatable.

        Args:
            locatable (Locatable): The locatable to create the graph node for.

        Returns:
            GraphNode: The graph node.
        """
        # TODO: make the imports at top or bottom of file
        from prodsys.simulation.resources import Resource
        from prodsys.simulation.port import Store

        existing_node = self.get_existing_graph_node_for_locatable(locatable)
        if existing_node:
            return existing_node

        new_graph_node = GraphNode(node_id=locatable.data.ID)
        self.nodes[locatable.data.ID] = new_graph_node
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
        return np.sqrt((node1[0] - node2[0]) ** 2 + (node1[1] - node2[1]) ** 2)

    def get_route_origin_and_target_locatables(
        self, request: request.Request, route_to_origin: bool
    ) -> Tuple[Optional[Locatable], Optional[Locatable]]:
        """
        Gets the origin and target locatable

        Args:
            request (request.Request): The transportation request.
            route_to_origin (bool): Indicates whether to find the route from current resource location to origin (True) or from origin to target of request (False).

        Returns:
            Tuple[Optional[Locatable], Optional[Locatable]]: A tuple containing the origin and target locatable objects for the transport request.
        """
        if route_to_origin:
            origin_locatable = request.resource.current_locatable
            target_locatable = request.origin
        else:
            origin_locatable = request.origin
            target_locatable = request.target
        return origin_locatable, target_locatable

    def get_route_origin_and_target(
        self, request: request.Request, route_to_origin: bool
    ) -> Tuple[Optional[GraphNode], Optional[GraphNode]]:
        """
        Converts the origin and target of the transport request to graph nodes.

        Args:
            request (Request): The transportation request.
            route_to_origin (bool): Indicates whether to find the route from current resource location to origin (True) or from origin to target of request (False).

        Returns:
            Tuple[Optional[GraphNode], Optional[GraphNode]]: A tuple containing the origin and target graph nodes for the transport request and the route_to_origin flag.
        """
        (
            origin_locatable,
            target_locatable,
        ) = self.get_route_origin_and_target_locatables(
            request=request, route_to_origin=route_to_origin
        )
        origin_graph_node = self.get_existing_graph_node_for_locatable(origin_locatable)
        target_graph_node = self.get_existing_graph_node_for_locatable(target_locatable)
        return origin_graph_node, target_graph_node

    def find_graphnode_path(
        self, origin: GraphNode, target: GraphNode, graph: Graph
    ) -> List[GraphNode]:
        """
        Finds the path between the origin and target graph nodes.

        Args:
            origin (GraphNode): The origin node.
            target (GraphNode): The target node.
            graph (Graph): The graph.

        Returns:
            The path as a list of graph nodes.
        """
        # Early termination if origin and target are the same
        if origin.node_id == target.node_id:
            return [origin]
            
        # Limit the number of nodes to prevent excessive computation
        if len(graph.nodes) > 100:  # Arbitrary limit to prevent infinite loops
            return []
            
        finder = DijkstraFinder()
        try:
            path, _ = finder.find_path(origin, target, graph)
            if path is None:
                return []
            return path
        except Exception:
            # If pathfinding fails, return empty path
            return []

    def convert_node_path_to_locatable_route(
        self, graph_node_path: List[GraphNode], links: List[List[Locatable]]
    ) -> List[Locatable]:
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
                    if (
                        node.node_id == locatable.data.ID
                        and locatable.data.ID not in seen_node_ids
                    ):
                        route.append(locatable)
                        seen_node_ids.append(locatable.data.ID)
        return route
