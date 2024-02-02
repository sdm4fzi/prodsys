from typing import List, TYPE_CHECKING, Optional, Union
from pathfinding.core.graph import Graph, GraphNode
from pathfinding.finder.dijkstra import DijkstraFinder

from prodsys.simulation import request

if TYPE_CHECKING:
    from prodsys.simulation import product, process, resources, request, sink, source

    
class Pathfinder:
    
    def __init__(self):

        # 1. Define a list of GraphNodes
        self.nodes: List[GraphNode] = []
        self.node_loc: List[Union[resources.NodeData, sink.Sink, source.Source]] = []

    def find_path(self, request: request.TransportResquest, which_path: bool):

        # 1. Calculates the edges
        edges = self.process_links_to_edges(request)
        graph = Graph(edges=edges, bi_directional=True)

        # 2. Transforms the origin & target location
        origin, target = self.origin_target_to_graphnode(request, graph, which_path)

        # 3. Calculates the find_graphNode_path
        g_path = self.find_graphnode_path(origin, target, graph)

        # 4. Transform the nodes of the path given from find_graphnode_path to a list of links
        path = self.node_path_to_link_path(g_path, request)

        return path
    

    def process_links_to_edges(self, request: request.TransportResquest):
        from prodsys.simulation import resources, sink, source
        # Firstly we create here the edges
        # Secondly we fill up the GraphsNodes list called nodes for the Graph later


        # given list of links
        given_links_list = request.process.links

        # list of edges correctly for pathfinder
        pathfinder_links = []

        for link in given_links_list:
            nn: List[Union[resources.NodeData, resources.Resource, sink.Sink, source.Source]] = []
            bb: List[GraphNode] = []
            for b_node in link:

                # node is needed 
                node = None

                # if node is existing we don't care and shouldnt get in the next step
                for y in self.nodes:
                    if isinstance(b_node, (sink.Sink, source.Source, resources.Resource)):
                        if y.node_id == b_node.data.ID:
                            node = y
                    else:
                        if y.node_id == b_node.ID:
                            node = y

                # if node is not existing add the node in self.nodes list.
                if node is None:
                    #TODO: Check if the list is globally filled up
                    if isinstance(b_node, (sink.Sink, source.Source, resources.Resource)):
                        node = GraphNode(node_id = b_node.data.ID)
                    else:
                        node = GraphNode(node_id = b_node.ID)
                    self.nodes.append(node)
                    self.node_loc.append(b_node)
                    
                nn.append(b_node)
                bb.append(node)


            # 9. Calculate the cost between the nodes and add the edge to the list
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

        #TODO: Return position_nodes as a list of nodes   
        return pathfinder_links
        

    def calculate_cost(self, node1, node2):
        # Calculates the costs between two nodes for the edge
        return abs(node1[0] - node2[0]) + abs(node1[1] - node2[1])
    

    def origin_target_to_graphnode(self, request: request.TransportResquest, graph: Graph, which_path: bool):
        from prodsys.simulation import resources, sink, source

        # 1. Check if the origin & target position is also a Link position
        matching_nodes = []
        #TODO: Aktuelle haben wir noch nicht das Problem das origin oder target ein Node sind
        # Sobald das der Fall ist dann muss die else mit .data. angepasst werden
        
        given_links_list = request.process.links
        for link in given_links_list:
            for nodex in link:
                # path is from agv to origin
                if which_path == True:
                    if isinstance(nodex, (resources.NodeData)):
                        for node in graph.nodes.values():
                            if nodex.ID == node.node_id:
                                # whether the agv is already at the origin then we wont be in this function
                                # or he at another station or node and we get his location so he moves to me
                                if (nodex.location == request.resource.get_location()) or (nodex.location == request.origin.data.location and nodex.ID == request.origin.data.ID):
                                    if node not in matching_nodes:
                                        matching_nodes.append(node)
                    else:
                        for node in graph.nodes.values():
                            if nodex.data.ID == node.node_id:
                                if (nodex.data.location == request.resource.get_location()) or (nodex.data.location == request.origin.data.location and nodex.data.ID == request.origin.data.ID):
                                    if node not in matching_nodes:
                                        matching_nodes.append(node)
                # path is from origin to target
                else:
                    if isinstance(nodex, (resources.NodeData)):
                        for node in graph.nodes.values():
                            if nodex.ID == node.node_id:
                                if node.node_id == request.origin.data.ID or node.node_id == request.target.data.ID:
                                    if node not in matching_nodes:
                                        matching_nodes.append(node)
                    else:
                        for node in graph.nodes.values():
                            if nodex.data.ID == node.node_id:
                                if node.node_id == request.origin.data.ID or node.node_id == request.target.data.ID:
                                    if node not in matching_nodes:
                                        matching_nodes.append(node)

        if len(matching_nodes) != 2:
            return ValueError("The origin or Target has no Link Position")
        
        origin, target = matching_nodes

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
        seen_ids = []

        for node in g_path:
            for link in given_links_list:
                for node_link in link:
                    if isinstance(node_link, (sink.Sink, source.Source, resources.Resource)):
                        if node.node_id == node_link.data.ID and node_link.data.ID not in seen_ids:
                            path.append(node_link)
                            seen_ids.append(node_link.data.ID)
                            
                    elif isinstance(node_link, (resources.NodeData)):
                        if node.node_id == node_link.ID and node_link.data.ID not in seen_ids:
                            path.append(node_link)
                            seen_ids.append(node_link.ID)

        return path
    
    



    

    
