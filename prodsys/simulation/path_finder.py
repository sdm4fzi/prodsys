from typing import List, TYPE_CHECKING, Optional
from pathfinding.core.graph import Graph, GraphNode
from pathfinding.finder.dijkstra import DijkstraFinder

from prodsys.simulation import request

if TYPE_CHECKING:
    from prodsys.simulation import product, process, resources, request

    
class Pathfinder:
    
    def __init__(self):

        # 1. Define a list of GraphNodes
        self.nodes: List[GraphNode] = {}
        # 2. Define a list of PositionNodes which includes also the position
        #TODO: return the position_nodes list also as a path for the Controller
        self.position_nodes = {}

    def find_path(self, request: request.TransportResquest):

        # 1. Calculates the edges
        edges = self.process_links_to_edges(request)
        graph = Graph(edges=edges, bi_directional=True)

        # 2. Transforms the origin & target location
        origin, target = self.origin_target_to_graphnode(self, request, graph)

        # 3. Calculates the find_graphNode_path
        graphnode_path = self.find_graphnode_path(self, origin, target, graph)

        # 4. Transform the nodes of the path given from find_graphnode_path to a list of links
        path = self.node_path_to_link_path(self, graphnode_path, links)

        return path
    

    def process_links_to_edges(self, request: request.TransportResquest):
        # Edges have startnode, endnode and cost, thats why links need to be transformed
        # With the edges it is possible to construct the Graph

        # 1. An empty list of edges is created
        edges = []
        links2 = request.process.process_data.links
        # 2. Iterate through all defined links
        for link in links:
            for b in links2:
                if link == b.ID:
                    # 3. Define a start_node & end_node as a Graphnode (just ID)
                    start_node = None
                    end_node = None
                    # 4. Define a position_start_node and position_end_node, which also includes the position (ID + position)
                    # Thats the LinkNode probably right?
                    position_start_node: links_data.Node = None
                    position_end_node = None
                    # 5. If the position and ID of the link already exist in the lists, do nothing
                    for node1 in self.position_nodes:
                        for nodea in self.nodes:
                            if node1.location == link.from_position and node1.ID == nodea.node_id:
                                position_start_node = node1
                                start_node = nodea
                                break

                    # 6. if no node exists with the location and link, then add the nodes to the lists    
                    if position_start_node is None:
                        position_start_node = links_data.Node(id = link.ID +"_start", position = link.from_position)
                        start_node = GraphNode(node_id = link.ID + "_start")
                        self.position_nodes.append(position_start_node)
                        self.nodes.append(start_node)          

                    # 7. If the position and ID of the link already exist in the lists, do nothing
                    for node2 in self.position_nodes:
                        for nodeb in self.nodes:
                            if node2.location == link.to_position and node2.ID == nodeb.node_id:
                                position_end_node = node2
                                end_node = nodeb
                                break
                            
                    # 8. if no node exists with the location and link, then add the nodes to the lists
                    if position_end_node is None:
                        position_end_node = links_data.Node(id = link.ID +"_end", position = link.to_position)
                        end_node = GraphNode(node_id = link.ID + "_end")
                        self.position_nodes.append(position_end_node)
                        self.nodes.append(end_node)

                    # 9. Calculate the cost between the nodes and add the edge to the list
                    cost = self.calculate_cost(self, position_start_node, position_end_node)       
                    edge = (start_node, end_node, cost)
                    edges.append(edge)

        #TODO: Return position_nodes as a list of nodes   
        return edges
        

    def calculate_cost(self, node1, node2):
        # Calculates the costs between two nodes for the edge
        return abs(node1.location[0] - node2.location[0]) + abs(node1.location[1] - node2.location[1])
    

    def origin_target_to_graphnode(self, request: request.TransportResquest, graph: Graph):
        # Transform the origin & target location of the request in a GraphNode

        # 1. Check if the origin & target position is also a Link position
        matching_nodes: List[links_data.Node] = []

        for node in self.position_nodes:
                if node.location == request.origin or node.location == request.target:
                        matching_nodes.append(node)

        if len(matching_nodes) != 2:
            return ValueError("The origin or Target has no Link Position")
        
        origin, target = matching_nodes

        # 2. Find the corresponding GraphNode for the origin & target position
        matching_graphnodes: List[GraphNode] = []
        for node in graph.nodes.values():
                if node.node_id == origin.ID or node.node_id == target.ID:
                        matching_graphnodes.append(node)
        
        origin, target = matching_graphnodes

        return origin, target
    
    def find_graphnode_path(self, origin: GraphNode, target: GraphNode, graph: Graph) -> List[GraphNode]:
        # maybe we can use the Nodes here for our logging
        finder = DijkstraFinder()
        path, _ = finder.find_path(origin, target, graph)
        return path
    

    def node_path_to_link_path(self, path: List[GraphNode], links):
        # Transform the nodes of the path given from find_graphnode_path to a list of links

        # 1. Create a list of the node ids (GraphNode) in order of the path: path_id
        path_graph_node: List[GraphNode] = []
        for node in path:
             path_graph_node.append(node)

        # 2. Create a list of nodes with positions (Nodes) in order of the path: path_id_position
        path_node: List[links_data.Node]= []
        for node in self.position_nodes:
             for nodeb in path_graph_node:
                if node.ID == nodeb.node_id:
                        path_node.append(node)

        # 3. Create an empty list of links: link_path
        link_path = []

        # 4. Iterate through the list path_id_position and match it with links
        for node in path_node:
             for link in links:
                     if (
                          link.from_position == node.location
                          or link.to_position == node.location
                     ) and link not in link_path:
                          link_path.append(link)
                          break
                     
        return link_path
    
    



    

    
