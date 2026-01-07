import shapely
import matplotlib.pyplot as plt


class Node:
    def __init__(self, position=None, shapely_point=None, node_orientation=None, node_type='None', corner_type='None', boundary_node=False, node_id=None):
        self.position = position
        self.shapely_point = shapely_point
        self.node_orientation = node_orientation
        self.node_type = node_type
        self.corner_type = corner_type
        self.boundary_node = boundary_node
        self.node_id = node_id


class Edge:
    def __init__(self, node1=None, node2=None, shapely_line=None, edge_type='None', boundary_edge=False,
                 direction='bi', cost=None, edge_id=None):
        self.node1 = node1
        self.node2 = node2
        self.shapely_line = shapely_line
        self.edge_type = edge_type
        self.boundary_edge = boundary_edge
        self.direction = direction
        self.cost = cost
        self.edge_id = edge_id


class Graph:
    def __init__(self):
        self.nodes = []  # List of node objects.
        self.edges = []  # List of edge objects.
        self.edges_on_nodes = {}  # Dictionary of edges on nodes.

        self.node_positions = []  # List of tuples with the positions of the nodes.
        self.node_points = []  # List of shapely Point objects representing the nodes.
        self.edges_nodes = []  # List of edges with the corresponding end nodes. End nodes are tuples of the node positions.
        self.edges_lines = []  # List of shapely LineString objects representing the edges.

        self.temporarily_removed_nodes = []  # List of temporarily removed node objects.
        self.temporarily_removed_edges = []  # List of temporarily removed edge objects.

    def add_node(self, position, shapely_point, node_type='None', corner_type='None', boundary_node=False,
                 node_id=None, temporary_node=None, orientation=None) -> None:
        """
        Add a node to the graph.

        Args:
            position (tuple): The position of the node as a tuple (x, y)..
            shapely_point (Point): The shapely Point object representing the node.
            node_type (str, optional): The type of the node. Defaults to None.
            node_id (str, optional): The unique identifier of the node. Defaults to None.
            temporary_node (Node, optional): The node to be added. Defaults to None.
            orientation (float, optional): The orientation of the node. Defaults to None.
        """
        if temporary_node is None:
            node = Node(position, shapely_point, orientation, node_type, corner_type, boundary_node, node_id)
        else:
            node = temporary_node
        self.nodes.append(node)
        self.node_positions.append(position)
        self.node_points.append(shapely_point)

    def remove_node(self, node, temporarily=False) -> None:
        """
        Remove a node from the graph.

        Args:
            node (Node): The node to be removed.
        """
        if node not in self.nodes:
            raise ValueError("Node not found in the graph.")

        self.nodes.remove(node)
        self.node_positions.remove(node.position)
        self.node_points.remove(node.shapely_point)

        # Remove edges containing this node, if edges are defined yet and the node is connected to edges.
        if self.edges != [] and node.position in self.edges_on_nodes.keys():
            edges_to_remove = self.edges_on_nodes[node.position].copy()
            for edge in edges_to_remove:
                if temporarily:
                    self.temporarily_removed_edges.append(edge)
                self.remove_edge(edge)

    def add_edge(self, node1, node2, shapely_line, edge_type='None', boundary_edge=False, direction='bi',
                 cost=None, edge_id=None, temporary_edge=None) -> None:
        """
        Add an edge to the graph and update the dictionary of edges on nodes.

        Args:
            node1 (Node): The first node of the edge.
            node2 (Node): The second node of the edge.
            shapely_line (LineString): The shapely LineString object representing the edge.
            edge_type (str, optional): The type of the edge. Defaults to None.
            direction (str, optional): The direction of the edge. Defaults to 'bi.
            cost (float, optional): The cost of the edge. Defaults to None.
            edge_id (str, optional): The unique identifier of the edge. Defaults to None.
            temporary_edge (Edge, optional): The edge to be added. Defaults to None.
        """
        if node1 not in self.nodes or node2 not in self.nodes:
            raise ValueError("Nodes not found in the graph.")

        if temporary_edge is None:
            edge = Edge(node1, node2, shapely_line, edge_type, boundary_edge, direction, cost, edge_id)
        else:
            edge = temporary_edge
        self.edges.append(edge)
        self.add_edges_per_node(edge)
        self.edges_nodes.append([node1.position, node2.position])
        self.edges_lines.append(shapely_line)

    def remove_edge(self, edge) -> None:
        """
        Remove an edge from the graph and update the dictionary of edges on nodes.

        Args:
            edge (Edge): The edge to be removed.
        """
        if edge not in self.edges:
            raise ValueError("Edge not found in the graph.")

        self.edges.remove(edge)
        self.remove_edges_per_node(edge)
        self.edges_nodes.remove([edge.node1.position, edge.node2.position])
        self.edges_lines.remove(edge.shapely_line)

    def add_edges_per_node(self, edge) -> None:
        """
        Adds an edge to the dictionary of edges on nodes.
        The dictionary is structured as follows: {node_position: [edge1, edge2, ...], ...}

        Args:
            edge (Edge): The edge to be added.
        """
        # Unidirectional edge from node 1 to node 2.
        if edge.direction == "1 -> 2":
            # Check if the first node of the edge is already in the dictionary.
            if edge.node1.position not in self.edges_on_nodes.keys():
                self.edges_on_nodes[edge.node1.position] = []
            # Add the edge to the list of edges for the first node.
            self.edges_on_nodes[edge.node1.position].append(edge)

        # Unidirectional edge from node 2 to node 1.
        elif edge.direction == "2 -> 1":
            # Check if the second node of the edge is already in the dictionary.
            if edge.node2.position not in self.edges_on_nodes.keys():
                self.edges_on_nodes[edge.node2.position] = []
            # Add the edge to the list of edges for the second node.
            self.edges_on_nodes[edge.node2.position].append(edge)

        # Bidirectional edge.
        elif edge.direction == "bi":
            # Check if the first node of the edge is already in the dictionary.
            if edge.node1.position not in self.edges_on_nodes.keys():
                self.edges_on_nodes[edge.node1.position] = []
            # Add the edge to the list of edges for the first node.
            self.edges_on_nodes[edge.node1.position].append(edge)

            # Check if the second node of the edge is already in the dictionary.
            if edge.node2.position not in self.edges_on_nodes.keys():
                self.edges_on_nodes[edge.node2.position] = []
            # Add the edge to the list of edges for the second node.
            self.edges_on_nodes[edge.node2.position].append(edge)

        else:
            raise ValueError("Edge direction not defined.")

    def remove_edges_per_node(self, edge) -> None:
        """
        Removes an edge from the dictionary of edges on nodes.

        Args:
            edge (Edge): The edge to be removed.
        """
        # Unidirectional edge from node 1 to node 2.
        if edge.direction == "1 -> 2":
            # Check if the edge is in the list of edges for the first node of the edge.
            if edge in self.edges_on_nodes[edge.node1.position]:
                self.edges_on_nodes[edge.node1.position].remove(edge)
                # If the list of edges for the first node of the edge is now empty, remove the node from the dictionary.
                if self.edges_on_nodes[edge.node1.position] == []:
                    del self.edges_on_nodes[edge.node1.position]

        # Unidirectional edge from node 2 to node 1.
        elif edge.direction == "2 -> 1":
            # Check if the edge is in the list of edges for the second node of the edge.
            if edge in self.edges_on_nodes[edge.node2.position]:
                self.edges_on_nodes[edge.node2.position].remove(edge)
                # If the list of edges for the second node of the edge is now empty, remove the node from the dictionary.
                if self.edges_on_nodes[edge.node2.position] == []:
                    del self.edges_on_nodes[edge.node2.position]

        # Bidirectional edge.
        elif edge.direction == "bi":
            # Check if the edge is in the list of edges for the first node of the edge.
            if edge in self.edges_on_nodes[edge.node1.position]:
                self.edges_on_nodes[edge.node1.position].remove(edge)
                # If the list of edges for the first node of the edge is now empty, remove the node from the dictionary.
                if self.edges_on_nodes[edge.node1.position] == []:
                    del self.edges_on_nodes[edge.node1.position]

            # Check if the edge is in the list of edges for the second node of the edge.
            if edge in self.edges_on_nodes[edge.node2.position]:
                self.edges_on_nodes[edge.node2.position].remove(edge)
                # If the list of edges for the second node of the edge is now empty, remove the node from the dictionary.
                if self.edges_on_nodes[edge.node2.position] == []:
                    del self.edges_on_nodes[edge.node2.position]

    def update_node_position(self, node_position, new_position,
                             check_clearance=False, node_edge_generator=None) -> bool:
        """
        Update the position of a node, the connected edges and the dictionary of edges on nodes.

        Args:
            node_position (tuple): The position of the node to be updated.
            new_position (tuple): The new position of the node.
        """
        # Update the node positions and shapely points list as well as the edges nodes and shapely lines list.
        # Check if the node exists in the node list.
        if node_position not in self.node_positions:
            raise ValueError("Node not found in the node list.")

        # Update the node positions and shapely points list.
        new_point = shapely.geometry.Point(new_position)
        self.node_positions[self.node_positions.index(node_position)] = new_position
        self.node_points[self.node_positions.index(new_position)] = new_point

        # Update the edges that are connected to the node.
        new_lines = []
        for edge_index, edge in enumerate(self.edges):
            # If the node is the first node of the edge.
            if node_position == edge.node1.position:
                # Update the edge nodes and shapely lines list.
                new_line = shapely.geometry.LineString([new_position, edge.node2.position])
                new_lines.append([new_line, [new_position, edge.node2.position]])
                self.edges_nodes[self.edges_nodes.index([node_position, edge.node2.position])] = [new_position, edge.node2.position]
                self.edges_lines[self.edges_nodes.index([new_position, edge.node2.position])] = new_line

            # If the node is the second node of the edge.
            elif node_position == edge.node2.position:
                # Update the edge nodes and shapely lines list.
                new_line = shapely.geometry.LineString([edge.node1.position, new_position])
                new_lines.append([new_line, [edge.node1.position, new_position]])
                self.edges_nodes[self.edges_nodes.index([edge.node1.position, node_position])] = [edge.node1.position, new_position]
                self.edges_lines[self.edges_nodes.index([edge.node1.position, new_position])] = new_line

        # Update the list of node and edge objects.
        # Initialize a variable to store the node to be updated.
        node = None
        for graph_node in self.nodes:
            if graph_node.position == node_position:
                node = graph_node
                break

        if node is None:
            raise ValueError("Node position not found in the graph.")

        # Update the position and shapely point of the node.
        node.position = new_position
        node.shapely_point = shapely.Point(new_position)

        # Update the shapely line of all edges that contain the node.
        for edge in self.edges:
            if edge.node1 == node or edge.node2 == node:
                edge.shapely_line = shapely.LineString([edge.node1.position, edge.node2.position])
                # If the old node position is a key in the dictionary of edges on nodes, update the key to the new node position.
                if node_position in self.edges_on_nodes.keys():
                    # Store the value of the old key.
                    value = self.edges_on_nodes[node_position]
                    # Create a new key with the stored value.
                    self.edges_on_nodes[new_position] = value
                    # Delete the old key.
                    del self.edges_on_nodes[node_position]

        clearance = True
        if check_clearance:
            # Find smallest node and edge distances apart from zero.
            node_distances = new_point.distance(self.node_points)
            min_node_distance = min([distance for distance in node_distances if distance > 0])

            if self.edges == []:
                # Set min_edge_distance to the required node edge clearance. No edges defined yet.
                min_edge_distance = node_edge_generator.required_node_edge_clearance

            else:
                edge_distances = new_point.distance(self.edges_lines)
                min_edge_distance = min([distance for distance in edge_distances if distance > 0])

            # Check node clearance.
            if not (new_point.within(node_edge_generator.table_config.table_configuration_polygon_cfree_round)
                    and min_node_distance >= node_edge_generator.required_node_clearance
                    and min_edge_distance >= node_edge_generator.required_node_edge_clearance):
                clearance = False

            # Check edge clearance.
            for line in new_lines:
                line_clearance, _ = node_edge_generator.check_line_clearance(line[1][0], line[1][1], line[0], update_node_position=True)
                if not line_clearance:
                    clearance = False

        if not clearance:
            # Undo the update of the node position.
            self.update_node_position(new_position, node_position)
            return False
        else:
            return True

    def update_node_and_edge_lists(self) -> None:
        """
        Update the node and edge lists of the graph based on the node and edge objects.
        """
        # Reset the node and edge lists.
        self.node_positions = []
        self.node_points = []
        self.edges_nodes = []
        self.edges_lines = []

        # Update the node and edge lists based on the node and edge objects.
        self.node_positions = [node.position for node in self.nodes]
        for node in self.nodes:
            node.shapely_point = shapely.Point(node.position)
        self.node_points = [node.shapely_point for node in self.nodes]
        self.edges_nodes = [[edge.node1.position, edge.node2.position] for edge in self.edges]
        for edge in self.edges:
            edge.shapely_line = shapely.LineString([edge.node1.position, edge.node2.position])
        self.edges_lines = [edge.shapely_line for edge in self.edges]

    def remove_redundant_nodes(self) -> None:
        """
        Function removes redundant nodes.
        """
        redundant_indices = []
        unique_positions = []
        for i, pos in enumerate(self.node_positions):
            if pos not in unique_positions:
                unique_positions.append(pos)
            else:
                redundant_indices.append(i)

        self.node_positions = unique_positions

        self.node_points = [self.node_points[i] for i in range(len(self.node_points)) if i not in redundant_indices]
        self.nodes = [self.nodes[i] for i in range(len(self.nodes)) if i not in redundant_indices]

    def remove_all_nodes_and_edges(self, nodes=True, edges=True) -> None:
        """
        Remove all nodes and edges from the graph.
        """
        if nodes:
            self.nodes = []
            self.node_positions = []
            self.node_points = []

        if edges:
            self.edges = []
            self.edges_on_nodes = {}
            self.edges_nodes = []
            self.edges_lines = []

    def remove_station_nodes_and_edges(self) -> None:
        """
        Remove all station nodes and edges from the graph.
        """
        all_nodes = self.nodes.copy()
        for node in all_nodes:
            if node.node_type == 'station':
                self.remove_node(node)

        all_edges = self.edges.copy()
        for edge in all_edges:
            if edge.edge_type == 'station <-> trajectory':
                self.remove_edge(edge)

    def remove_all_edges_except_boundary(self) -> None:
        """
        Remove all edges from the graph except the boundary edges.
        """
        all_edges = self.edges.copy()
        for edge in all_edges:
            if not edge.boundary_edge:
                self.remove_edge(edge)

    def remove_not_used_nodes_and_edges(self, nodes: list = [], edges: list = [], keep_boundary: bool = False) -> None:
        """
        Remove all nodes and edges from the graph that are not in the lists of used nodes and edges.

        nodes: list of nodes that should be kept.
        edges: list of edges that should be kept.
        keep_boundary: If True, boundary nodes and edges are not removed.
        """
        all_nodes = self.nodes.copy()
        for node in all_nodes:
            if node not in nodes:
                if keep_boundary and node.boundary_node:
                    # If boundary nodes are kept, they are not removed.
                    continue
                # If nodes are removed, all connected edges are removed automatically.
                self.remove_node(node)

        all_edges = self.edges.copy()
        for edge in all_edges:
            if edge not in edges:
                if keep_boundary and edge.boundary_edge:
                    # If boundary edges are kept, they are not removed.
                    continue
                self.remove_edge(edge)

    def remove_nodes_and_edges_temporarily(self, corner_nodes_list, visualization) -> None:
        """
        Removes nodes and edges that are within the polygons defined by the list of corner nodes temporarily.
        Can be used when a vehicle is defect or other obstacles are in the way.
        """
        for corner_nodes in corner_nodes_list:
            # Define polygon.
            polygon = shapely.geometry.Polygon(corner_nodes)

            # Draw polygon to visualization.
            if "obstacle_layer" not in visualization.occupancy_matrices.keys():
                visualization.add_free_layer("obstacle_layer")
            visualization.draw_polygon_to_layer("obstacle_layer", corner_nodes, value=0.55)

            # Expand polygon by required boundary clearance.
            polygon = polygon.buffer(16)

            # Remove nodes.
            node_count = len(self.nodes)
            removed_nodes = 0
            for node_index in range(node_count):
                if self.nodes[node_index - removed_nodes].shapely_point.within(polygon):
                    self.temporarily_removed_nodes.append(self.nodes[node_index - removed_nodes])
                    self.remove_node(self.nodes[node_index - removed_nodes], temporarily=True)
                    removed_nodes += 1

            # Remove edges.
            edge_count = len(self.edges)
            removed_edges = 0
            for edge_index in range(edge_count):
                if self.edges[edge_index - removed_edges].shapely_line.within(polygon) \
                        or self.edges[edge_index - removed_edges].shapely_line.intersects(polygon):
                    self.temporarily_removed_edges.append(self.edges[edge_index - removed_edges])
                    self.remove_edge(self.edges[edge_index - removed_edges])
                    removed_edges += 1

    def add_temporarily_removed_nodes_and_edges(self, corner_nodes_list, visualization) -> None:
        """
        Add temporarily removed nodes and edges due to defect vehicles or obstacles.
        """
        for corner_nodes in corner_nodes_list:
            # Remove polygon from visualization.
            visualization.draw_polygon_to_layer("obstacle_layer", corner_nodes, value=0)

            nodes_to_add = self.temporarily_removed_nodes.copy()
            for node in nodes_to_add:
                self.add_node(node.position, node.shapely_point, node.node_type, temporary_node=node)
                self.temporarily_removed_nodes.remove(node)

            edges_to_add = self.temporarily_removed_edges.copy()
            for edge in edges_to_add:
                self.add_edge(edge.node1, edge.node2, edge.shapely_line, edge.edge_type, temporary_edge=edge)
                self.temporarily_removed_edges.remove(edge)

    def update_graph_connections(self) -> None:
        """
        Constructs a dictionary of edges on nodes.
        The dictionary is structured as follows: {node_position: [edge1, edge2, ...], ...}

        Args:
            None
        """
        # Initialize an empty dictionary to store the edges on nodes.
        self.edges_on_nodes = {}

        for edge in self.edges:
            # For each edge, add it to the corresponding node's list of edges in the dictionary.
            self.add_edges_per_node(edge)

    def reset_all_node_and_edge_types(self):
        """
        Reset the type of all nodes and edges.
        """
        for node in self.nodes:
            node.node_type = 'None'
        for edge in self.edges:
            edge.edge_type = 'None'

    def get_transportation_tasks(self, layouts, layout_nr) -> dict:
        """
        Function returns the start and goal lists for transportation tasks as a dictionary.
        Start and goal positions are loaded from the production layouts and the corresponding node IDs are determined.
        The returned lists are lists of lists containing the node IDs of the start and goal positions.
        First entry in the start list corresponds to the first entry in the goal list and so on.
        For each layout several transportation tasks are defined.
        starts_lists is a list of lists, where each list contains the node IDs of the start nodes for one transportation task.
        """
        starts_lists = []
        goals_lists = []
        starts_pos_lists, goals_pos_lists = layouts.production_layouts_transportation_tasks(layout_nr)

        # Get the node IDs of the start and goal positions.
        for starts_pos_list in starts_pos_lists:
            starts = []
            for start_pos in starts_pos_list:
                start_node = self.nodes[self.node_positions.index(start_pos)]
                # starts.append(start_node.node_id)
                starts.append(list(start_node.position))
            starts_lists.append(starts)

        for goals_pos_list in goals_pos_lists:
            goals = []
            for goal_pos in goals_pos_list:
                goal_node = self.nodes[self.node_positions.index(goal_pos)]
                # goals.append(goal_node.node_id)
                goals.append(list(goal_node.position))
            goals_lists.append(goals)

        # Check if lengths of start and goal lists are equal.
        for i in range(len(starts_lists)):
            if len(starts_lists[i]) != len(goals_lists[i]):
                raise ValueError("Lengths of start and goal lists are not equal.")

        starts_goals_lists = {
            "starts_lists": [starts_lists[0], starts_lists[1], starts_lists[2]],
            "goals_lists": [goals_lists[0], goals_lists[1], goals_lists[2]]
        }

        return starts_goals_lists

    def analyze_graph(self, graph) -> None:
        """
        Function analyzes the graph and plots a histogram of the number of node connections per node.

        Args:
            graph (dict): The graph to be analyzed. The dictionary is structured as follows: {node_position: [edge1, edge2, ...], ...}
        """
        # Create a dictionary where the keys are the node positions and the values are the number of connections for each node.
        number_of_node_connections_per_node = {key: len(value) for key, value in graph.edges_on_nodes.items()}

        # Create a dictionary where the keys are the number of connections
        # and the values are the number of nodes with that number of connections.
        number_of_node_connections_absolute_count = {}
        for key, value in number_of_node_connections_per_node.items():
            if value not in number_of_node_connections_absolute_count.keys():
                number_of_node_connections_absolute_count[value] = 1
            else:
                number_of_node_connections_absolute_count[value] += 1

        # Get the list of number of connections (positions on the x-axis of the histogram).
        positions = list(number_of_node_connections_absolute_count.keys())
        # Get the list of number of nodes with that number of connections (heights of the bars on the histogram).
        heights = list(number_of_node_connections_absolute_count.values())

        # Create a new figure and plot the histogram.
        plt.figure(figsize=(10, 7))
        plt.bar(positions, heights, color='blue', edgecolor='black')
        plt.xlabel('Anzahl Kanten an Knoten / Vernetzungsgrad')
        plt.ylabel('Anzahl Knoten / Häufigkeit')
        plt.title('Histogramm')
        plt.show()
