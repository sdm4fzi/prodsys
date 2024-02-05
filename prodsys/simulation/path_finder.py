from typing import List, TYPE_CHECKING, Optional, Union
from pathfinding.core.graph import Graph, GraphNode
from pathfinding.finder.dijkstra import DijkstraFinder

from prodsys.simulation import request

if TYPE_CHECKING:
    from prodsys.simulation import product, process, resources, request, sink, source

    
class Pathfinder:
    
    def __init__(self):

        self.nodes: List[GraphNode] = []
        self.node_loc: List[Union[resources.NodeData, sink.Sink, source.Source]] = []

    def find_path(self, request: request.TransportResquest, which_path: bool):

        edges = self.process_links_to_edges(request)
        graph = Graph(edges=edges, bi_directional=True)
        origin, target = self.origin_target_to_graphnode(request, graph, which_path)
        g_path = self.find_graphnode_path(origin, target, graph)
        path = self.node_path_to_link_path(g_path, request)

        return path
    

    def process_links_to_edges(self, request: request.TransportResquest):
        from prodsys.simulation import resources, sink, source

        given_links_list = request.process.links
        pathfinder_links = []

        for link in given_links_list:
            nn: List[Union[resources.NodeData, resources.Resource, sink.Sink, source.Source]] = []
            bb: List[GraphNode] = []
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
                    if isinstance(b_node, (sink.Sink, source.Source, resources.Resource)):
                        node = GraphNode(node_id = b_node.data.ID)
                    else:
                        node = GraphNode(node_id = b_node.ID)
                    self.nodes.append(node)
                    self.node_loc.append(b_node)
                    
                nn.append(b_node)
                bb.append(node)

            if isinstance(nn[0], (sink.Sink, source.Source, resources.Resource)) and isinstance(nn[1], ( sink.Sink, source.Source, resources.Resource)):
                cost = self.calculate_cost(nn[0].data.location, nn[1].data.location)
            elif isinstance(nn[0], (sink.Sink, source.Source, resources.Resource)) and isinstance(nn[1], (resources.NodeData)):
                cost = self.calculate_cost(nn[0].data.location, nn[1].location)
            elif isinstance(nn[0], (resources.NodeData)) and isinstance(nn[1], ( sink.Sink, source.Source, resources.Resource)):
                cost = self.calculate_cost(nn[0].location, nn[1].data.location)
            else:
                cost = self.calculate_cost(nn[0].location, nn[1].location)

            edge = (bb[0], bb[1], cost)
            pathfinder_links.append(edge)

        return pathfinder_links
        

    def calculate_cost(self, node1, node2):
        # Calculates the costs between two nodes for the edge
        return abs(node1[0] - node2[0]) + abs(node1[1] - node2[1])
    

    def origin_target_to_graphnode(self, request: request.TransportResquest, graph: Graph, which_path: bool):
        from prodsys.simulation import resources

        origin, target = None, None
        given_links_list = request.process.links

        for link in given_links_list:
            for nodex in link:
                if which_path == True: # path from agv to origin
                    if isinstance(nodex, (resources.NodeData)):
                        for node in graph.nodes.values():
                            if nodex.ID == node.node_id:
                                if (nodex.location == request.resource.get_location()):
                                    if origin is None:
                                        origin = node
                                elif (nodex.location == request.origin.data.location and nodex.ID == request.origin.data.ID):
                                    if target is None:
                                        target = node
                    else: # node is a resource|sinks|source
                        for node in graph.nodes.values():
                            if nodex.data.ID == node.node_id:
                                if (nodex.data.location == request.resource.get_location()):
                                    if origin is None:
                                        origin = node
                                elif (nodex.data.location == request.origin.data.location and nodex.data.ID == request.origin.data.ID):
                                    if target is None:
                                        target = node
                else: # path from origin to target
                    if isinstance(nodex, (resources.NodeData)):
                        for node in graph.nodes.values():
                            if nodex.ID == node.node_id:
                                if (nodex.location == request.origin.data.location and nodex.ID == request.origin.data.ID):
                                    if origin is None:
                                        origin = node
                                elif (nodex.location == request.target.data.location and nodex.ID == request.target.data.ID):
                                    if target is None:
                                        target = node
                    else: # node is a resource|sinks|source
                        for node in graph.nodes.values():
                            if nodex.data.ID == node.node_id:
                                if (nodex.data.location == request.origin.data.location and nodex.data.ID == request.origin.data.ID):
                                    if origin is None:
                                        origin = node
                                elif(nodex.data.location == request.target.data.location and nodex.data.ID == request.target.data.ID):
                                    if target is None:
                                        target = node

        return origin, target
    
    def find_graphnode_path(self, origin: GraphNode, target: GraphNode, graph: Graph) -> List[GraphNode]:
        # maybe we can use the Nodes here for our logging
        finder = DijkstraFinder()
        path, _ = finder.find_path(origin, target, graph)
        return path
    

    def node_path_to_link_path(self, g_path: List[GraphNode], request: request.TransportResquest):
        from prodsys.simulation import resources, sink, source
        # Transform the nodes of the path given from find_graphnode_path to a list of links

        # 1. Create a list of the node ids (GraphNode) in order of the path: path_id
        given_links_list = request.process.links
        path = []
        seen_ids = [] # no node several times  in the path

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
    
    



    

    
