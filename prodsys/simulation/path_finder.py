from typing import List, TYPE_CHECKING, Optional, Union
from pathfinding.core.graph import Graph, GraphNode
from pathfinding.finder.dijkstra import DijkstraFinder

from prodsys.simulation import request

if TYPE_CHECKING:
    from prodsys.simulation import resources, request, sink, source, process

class Pathfinder:
    """
    Class representing a path finder for transportation requests in a graph.
    """

    def __init__(self):
        """
        Initializes two empty lists of nodes and node locations.
        """
        self.nodes: List[GraphNode] = []
        self.node_loc: List[Union[resources.NodeData, sink.Sink, source.Source]] = []

    def find_path(self, request: request.TransportResquest, which_path: bool, self_obj):
        """
        The general function which includes all sub functions to find the shortest path for a TransportRequest.

        Args:
            request (TransportResquest): The transportation request.
            which_path (bool): Indicates whether to find the path from AGV to origin or from origin to target.
            self_obj: The process of the related resource

        Returns:
            The path as a list of links.
        """
        given_links_list = self_obj.links

        edges = self.process_links_to_edges(request, given_links_list=given_links_list)
        graph = Graph(edges=edges, bi_directional=True)
        origin, target = self.origin_target_to_graphnode(request, graph, which_path, given_links_list=given_links_list)
        if origin is None or target is None:
            return False
        g_path = self.find_graphnode_path(origin, target, graph)
        path = self.node_path_to_link_path(g_path, request, given_links_list=given_links_list)

        return path

    def process_links_to_edges(self, request: request.TransportResquest, given_links_list):
        """
        Processes the given links to create (Graph)-edges for the graph.

        Args:
            request (TransportResquest): The transportation request.
            given_links_list: The given links list.

        Returns:
            The edges as a list of tuples (with a start_node, end_node and related costs).
        """
        from prodsys.simulation import resources, sink, source
        pathfinder_edges = []

        for link in given_links_list:
            link_edge: List[Union[resources.NodeData, resources.Resource, sink.Sink, source.Source]] = []
            graphnode_edge: List[GraphNode] = []
            self.make_list(link, link_edge, graphnode_edge)
            if isinstance(link_edge[0], (sink.Sink, source.Source, resources.Resource)) and isinstance(link_edge[1], (sink.Sink, source.Source, resources.Resource)):
                cost = self.calculate_cost(link_edge[0].data.location, link_edge[1].data.location)
            elif isinstance(link_edge[0], (sink.Sink, source.Source, resources.Resource)) and isinstance(link_edge[1], (resources.NodeData)):
                cost = self.calculate_cost(link_edge[0].data.location, link_edge[1].location)
            elif isinstance(link_edge[0], (resources.NodeData)) and isinstance(link_edge[1], (sink.Sink, source.Source, resources.Resource)):
                cost = self.calculate_cost(link_edge[0].location, link_edge[1].data.location)
            else:
                cost = self.calculate_cost(link_edge[0].location, link_edge[1].location)

            edge = (graphnode_edge[0], graphnode_edge[1], cost)
            pathfinder_edges.append(edge)

        return pathfinder_edges
    
    def make_list(self, link, link_edge, graphnode_edge):
        """
        Creates a list of links and edges.

        Args:
            link (list): A list of nodes.
            link_edge (list): A list to store the link edges.
            graphnode_edge (list): A list to store the graph node edges.

        Returns:
            None
        """

        from prodsys.simulation import resources, sink, source

        for b_node in link:
            node = None
            for y in self.nodes:
                if isinstance(b_node, (sink.Sink, source.Source, resources.Resource)):
                    if y.node_id == b_node.data.ID:
                        node = y
                else:
                    if y.node_id == b_node.ID:
                        node = y
            
            if node is None:
                node_id = b_node.data.ID if isinstance(b_node, (sink.Sink, source.Source, resources.Resource)) else b_node.ID
                node = GraphNode(node_id=node_id)
                self.nodes.append(node)
                self.node_loc.append(b_node)

            link_edge.append(b_node)
            graphnode_edge.append(node)

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

    def origin_target_to_graphnode(self, request: request.TransportResquest, graph: Graph, which_path: bool, given_links_list):
        """
        Converts the origin and target of the transport request to graph nodes.

        Args:
            request (TransportResquest): The transportation request.
            graph (Graph): The graph.
            which_path (bool): Indicates whether to find the path from AGV to origin or from origin to target.
            given_links_list: The given links list.

        Returns:
            The origin and target as graph nodes.
        """
        origin, target = None, None
        for link in given_links_list:
            for nodex in link:
                origin, target = self.create_graphnodes(nodex, which_path, request, graph, origin, target)
        return origin, target
    
    def create_graphnodes(self, nodex, which_path, request, graph, origin, target):
        """
        Creates graph nodes for the origin and target.

        Args:
            nodex (object): The node object.
            which_path (bool): Indicates whether it is a path from agv to origin or from origin to target.
            request (object): The request object.
            graph (object): The graph object.
            origin (object): The origin node.
            target (object): The target node.

        Returns:
            tuple: A tuple containing the origin and target nodes.
        """
        from prodsys.simulation import resources
        for node in graph.nodes.values():
            if isinstance(nodex, (resources.NodeData)):
                if nodex.ID != node.node_id:
                    continue
                if which_path:  # path from agv to origin
                    if nodex.location != request.resource.get_location() and not (nodex.location == request.origin.data.location and nodex.ID == request.origin.data.ID):
                        continue
                else:  # path from origin to target
                    if not (nodex.location == request.origin.data.location and nodex.ID == request.origin.data.ID) and not (nodex.location == request.target.data.location and nodex.ID == request.target.data.ID):
                        continue
            else:  # node is a resource|sinks|source
                if nodex.data.ID != node.node_id:
                    continue
                if which_path:  # path from agv to origin
                    if nodex.data.location != request.resource.get_location() and not (nodex.data.location == request.origin.data.location and nodex.data.ID == request.origin.data.ID):
                        continue
                else:  # path from origin to target
                    if not (nodex.data.location == request.origin.data.location and nodex.data.ID == request.origin.data.ID) and not (nodex.data.location == request.target.data.location and nodex.data.ID == request.target.data.ID):
                        continue

            if origin is None:
                origin = node
            elif target is None:
                target = node

        return origin, target

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

    def node_path_to_link_path(self, g_path: List[GraphNode], request: request.TransportResquest, given_links_list):
        """
        Converts the path of graph nodes to a path of links.

        Args:
            g_path (List[GraphNode]): The path as a list of graph nodes.
            request (TransportResquest): The transportation request.
            given_links_list: The given links list.

        Returns:
            The path as a list of links.
        """
        from prodsys.simulation import resources, sink, source
        path = []
        seen_ids = []  # no node several times in the path

        for node in g_path:
            for link in given_links_list:
                for node_link in link:
                    if isinstance(node_link, (resources.NodeData)):
                        if node.node_id == node_link.ID and node_link.ID not in seen_ids:
                            path.append(node_link)
                            seen_ids.append(node_link.ID)
                    elif isinstance(node_link, (sink.Sink, source.Source, resources.Resource)):
                        if node.node_id == node_link.data.ID and node_link.data.ID not in seen_ids:
                            path.append(node_link)
                            seen_ids.append(node_link.data.ID)

        return path
    