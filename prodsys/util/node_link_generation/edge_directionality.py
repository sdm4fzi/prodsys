import math


class EdgeDirectionality:
    """
    This class is used to determine the directionality of an edge in a graph.
    """

    def __init__(self, table_config, node_edge_generator) -> None:
        """
        Constructor for the EdgeDirectionality class.
        """
        self.table_config = table_config
        self.graph = node_edge_generator.graph

    def define_boundary_edges_directionality(self, exterior_direction='ccw', narrow_sections_unidirectional=False) -> None:
        """
        Determines the directionality of the boundary edges. The directionality of the exterior boundary is passed.
        The directionality of the interior boundaries is the opposite of the exterior boundary.

        Parameters
        ----------
        exterior_direction : str
            The exterior_direction of the exterior boundary edges. Either clockwise ('cw') or counter-clockwise ('ccw').
        narrow_sections_unidirectional : bool
            If True, the narrow sections are unidirectional. If False, the narrow sections are bidirectional.
        """
        # Extract the boundary nodes and edges.
        boundary_nodes = [node for node in self.graph.nodes if node.boundary_node]
        boundary_edges = [edge for edge in self.graph.edges if edge.boundary_edge]

        # Initialize.
        visited_edges_total = set()
        visited_edges_set_to_bi = []

        for boundary_index, corner_nodes in enumerate(self.table_config.table_configuration_corner_nodes_cfree):
            # Reset.
            current_node = None
            current_edge = None
            visited_edges_boundary = []
            visited_edges_boundary_twice = []

            if boundary_index != 0:
                # Interior boundary. Direction of exterior and interior boundary should be different.
                interior_boundary = True
                if exterior_direction == 'ccw':
                    direction = 'cw'
                else:
                    direction = 'ccw'
            else:
                # Exterior boundary.
                interior_boundary = False
                direction = exterior_direction

            # Lower left node is the origin node.
            origin_node_position = corner_nodes[0]

            # Find the closest node of the boundary nodes to the origin node. This node is the start node.
            node_distances = [math.dist(origin_node_position, node.position) for node in boundary_nodes]
            min_index = node_distances.index(min(node_distances))
            start_node = boundary_nodes[min_index]

            # Determine the direction of the boundary edges.
            while current_node != start_node:
                # List, [node, relative angle, position of node in edge, edge].
                connected_boundary_nodes = []

                if current_node is None:
                    # First iteration.
                    current_node = start_node

                # Find the edges that are connected to the current node.
                #if current_node.position in self.graph.edges_on_nodes.keys():
                connected_boundary_edges = [edge for edge in self.graph.edges_on_nodes[current_node.position] if edge in boundary_edges]
                for edge in connected_boundary_edges:
                    if edge.node1 == current_node:
                        connected_boundary_nodes.append([edge.node2, None, '2', edge])
                    else:
                        connected_boundary_nodes.append([edge.node1, None, '1', edge])
                #else:
                #    raise ValueError('No connected boundary edges found in definition of boundary edges directionality.')

                # Calculate the relative angle between the current edge and each connected edge.
                # Replace the second entries of connected_boundary_nodes with the relative angles.
                for edge_index, connected_boundary_node in enumerate(connected_boundary_nodes):
                    if connected_boundary_node[3] == current_edge and current_edge is not None:
                        # Same edge. Angle is pi or -pi. Should be the least likely case.
                        if interior_boundary:
                            # Relative to the right.
                            connected_boundary_nodes[edge_index][1] = -math.pi
                        else:
                            # Relative to the left.
                            connected_boundary_nodes[edge_index][1] = math.pi
                        continue

                    # Determine the nodes of the connected (new) edge.
                    if connected_boundary_node[2] == '1':
                        new_edge_nodes = [connected_boundary_node[3].node2, connected_boundary_node[0]]
                    elif connected_boundary_node[2] == '2':
                        new_edge_nodes = [connected_boundary_node[3].node1, connected_boundary_node[0]]

                    if current_edge is not None:
                        # Determine the nodes of the current edge.
                        if current_edge.node1 in new_edge_nodes:
                            current_edge_nodes = [current_edge.node2, current_edge.node1]
                        elif current_edge.node2 in new_edge_nodes:
                            current_edge_nodes = [current_edge.node1, current_edge.node2]

                        # Calculate the relative angle between the current edge and the new edge.
                        relative_angle = self.calculate_angle(current_edge_nodes, new_edge_nodes)

                    else:
                        # First iteration. There is no current edge.
                        # Calculate the relative angle between the first segment of the boundary and each connected edge.
                        current_edge_nodes = [corner_nodes[0], corner_nodes[1]]

                        # Calculate the relative angle between the first segment of the boundary and the new edge.
                        relative_angle = self.calculate_angle(current_edge_nodes, new_edge_nodes, first_iteration=True)

                    # Store the relative angle.
                    connected_boundary_nodes[edge_index][1] = relative_angle

                # Sort the connected boundary nodes by the relative angles of the edges.
                if interior_boundary and current_edge is not None:
                    # Interior boundary.
                    # Order the edges by the relative angle. The first edge is the one pointing the most to the left relatively.
                    connected_boundary_nodes.sort(key=lambda x: x[1], reverse=True)
                elif current_edge is not None:
                    # Exterior boundary.
                    # Order the edges by the relative angle. The first edge is the one pointing the most to the right relatively.
                    connected_boundary_nodes.sort(key=lambda x: x[1])
                else:
                    # First iteration, interior od exterior boundary.
                    # Order the edges by the relative angle. The first edge is the one with the smallest relative angle difference
                    # to the first segment of the boundary.
                    connected_boundary_nodes.sort(key=lambda x: abs(x[1]))

                # Make a copy in case all edges have been visited already.
                connected_boundary_nodes_copy = connected_boundary_nodes.copy()

                # Remove the edges that have already been visited for that edge.
                for connected_node in connected_boundary_nodes_copy:
                    if connected_node[3] in visited_edges_boundary:
                        connected_boundary_nodes.remove(connected_node)

                all_edges_visited = False
                if len(connected_boundary_nodes) == 0:
                    all_edges_visited = True

                if all_edges_visited:
                    # Edge is visited the second time.
                    if connected_boundary_nodes_copy[0][3] == current_edge and len(connected_boundary_nodes_copy) > 1:
                        connected_boundary_nodes_copy.pop(0)

                    # Update current node, current edge and visited edges.
                    # Also check if edge has already been visited twice for that boundary.
                    current_edge = None
                    for connected_boundary_node in connected_boundary_nodes_copy:
                        if connected_boundary_node[3] not in visited_edges_boundary_twice:
                            # Select an edge that is not visited twice.
                            current_edge = connected_boundary_node[3]
                            break
                    if current_edge is None:
                        # All edges are visited twice.
                        current_edge = connected_boundary_nodes_copy[0][3]
                    if current_edge in visited_edges_boundary_twice:
                        raise ValueError('Error in definition of directionality of boundary edges. Edge visited the third time.')
                    elif current_edge in visited_edges_boundary:
                        visited_edges_boundary_twice.append(current_edge)
                    else:
                        visited_edges_boundary.append(current_edge)
                    current_node = connected_boundary_nodes_copy[0][0]

                    # If the edge is already set to 'bi', it remains 'bi'.
                    if current_edge in visited_edges_set_to_bi:
                        current_edge.direction = 'bi'

                    # If edge is visited the second time for this boundary, the direction must be set to 'bi'.
                    elif connected_boundary_nodes_copy[0][2] == '1':
                        if direction == 'ccw' and current_edge.direction != '2 -> 1':
                            if current_edge in visited_edges_boundary_twice or not narrow_sections_unidirectional:
                                visited_edges_set_to_bi.append(current_edge)
                                current_edge.direction = 'bi'
                        elif direction == 'cw' and current_edge.direction != '1 -> 2':
                            if current_edge in visited_edges_boundary_twice or not narrow_sections_unidirectional:
                                visited_edges_set_to_bi.append(current_edge)
                                current_edge.direction = 'bi'

                    elif connected_boundary_nodes_copy[0][2] == '2':
                        if direction == 'ccw' and current_edge.direction != '1 -> 2':
                            if current_edge in visited_edges_boundary_twice or not narrow_sections_unidirectional:
                                visited_edges_set_to_bi.append(current_edge)
                                current_edge.direction = 'bi'
                        elif direction == 'cw' and current_edge.direction != '2 -> 1':
                            if current_edge in visited_edges_boundary_twice or not narrow_sections_unidirectional:
                                visited_edges_set_to_bi.append(current_edge)
                                current_edge.direction = 'bi'

                elif not all_edges_visited:
                    # Edge is visited the first time.

                    # Update current node, current edge and visited edges.
                    current_edge = connected_boundary_nodes[0][3]
                    visited_edges_boundary.append(current_edge)
                    visited_edges_total.add(current_edge)
                    current_node = connected_boundary_nodes[0][0]

                    # If the edge is already set to 'bi', it remains 'bi'.
                    if current_edge in visited_edges_set_to_bi:
                        current_edge.direction = 'bi'

                    # First set direction is prioritized.
                    # Direction is set to 'bi' depending on narrow_sections_unidirectional, if it was set unidirectional before.
                    elif connected_boundary_nodes[0][2] == '1':
                        if direction == 'ccw' and current_edge.direction == 'bi':
                            current_edge.direction = '2 -> 1'
                        elif direction == 'ccw' and current_edge.direction == '1 -> 2' and not narrow_sections_unidirectional:
                            current_edge.direction = 'bi'
                        elif direction == 'cw' and current_edge.direction == 'bi':
                            current_edge.direction = '1 -> 2'
                        elif direction == 'cw' and current_edge.direction == '2 -> 1' and not narrow_sections_unidirectional:
                            current_edge.direction = 'bi'
                    elif connected_boundary_nodes[0][2] == '2':
                        if direction == 'ccw' and current_edge.direction == 'bi':
                            current_edge.direction = '1 -> 2'
                        elif direction == 'ccw' and current_edge.direction == '2 -> 1' and not narrow_sections_unidirectional:
                            current_edge.direction = 'bi'
                        elif direction == 'cw' and current_edge.direction == 'bi':
                            current_edge.direction = '2 -> 1'
                        elif direction == 'cw' and current_edge.direction == '1 -> 2' and not narrow_sections_unidirectional:
                            current_edge.direction = 'bi'

        if len(visited_edges_total) != len(boundary_edges):
            raise ValueError('Error in definition of directionality of boundary edges. Not all boundary edges have been visited.')

    def define_paths_edges_directionality(self, paths_edges_directions, directions_matching=True) -> None:
        """
        Function defines the directionality of the edges based on the planned paths.

        paths_edges_directions: Dictionary with edges as keys and a list of directions as values.
        directions_matching: If True, all directions of the list must be the same in order to define the direction as unidirectional.
                             If False, the direction is defined based on the majority of the directions in the list.
        """
        for edge, directions in paths_edges_directions.items():
            if directions_matching:
                # Unidirectional.
                if len(set(directions)) == 1:
                    if directions[0] == '1 -> 2':
                        edge.direction = '1 -> 2'
                    elif directions[0] == '2 -> 1':
                        edge.direction = '2 -> 1'
                    else:
                        raise ValueError('Error in definition of directionality of edges based on paths. Invalid direction.')
                else:
                    edge.direction = 'bi'
            else:
                # Bidirectional.
                if directions.count('1 -> 2') > directions.count('2 -> 1'):
                    edge.direction = '1 -> 2'
                elif directions.count('1 -> 2') < directions.count('2 -> 1'):
                    edge.direction = '2 -> 1'
                else:
                    edge.direction = 'bi'

    def define_boundary_nodes_and_edges(self) -> None:
        """
        Determines the boundary nodes and edges of the graph.
        """
        # Track all assigned boundary nodes and edges.
        boundary_nodes = set()
        boundary_edges = set()

        # Extract the boundary nodes and edges.
        for boundary_index, corner_nodes in enumerate(self.table_config.table_configuration_corner_nodes_cfree):
            # Reset.
            current_node = None
            current_edge = None
            visited_edges_boundary = []
            visited_edges_boundary_twice = []

            if boundary_index != 0:
                # Interior boundary. Direction of exterior and interior boundary should be different.
                interior_boundary = True

            else:
                # Exterior boundary.
                interior_boundary = False

            # Lower left node is the origin node.
            origin_node_position = corner_nodes[0]

            # Find the closest node of the boundary nodes to the origin node. This node is the start node.
            # TODO: Find a better solution to define the start node.
            node_distances = [math.dist(origin_node_position, node.position) for node in self.graph.nodes]
            min_index = node_distances.index(min(node_distances))
            start_node = self.graph.nodes[min_index]
            while start_node.node_type == 'station':
                # Find next closest node.
                node_distances.pop(min_index)
                min_index = node_distances.index(min(node_distances))
                start_node = self.graph.nodes[min_index]

            # Determine the boundary nodes and edges.
            while current_node != start_node:
                # List, [node, relative angle, position of node in edge, edge].
                connected_boundary_nodes = []

                if current_node is None:
                    # First iteration.
                    current_node = start_node

                # Find the edges that are connected to the current node.
                # if current_node.position in self.graph.edges_on_nodes.keys():
                connected_boundary_edges = self.graph.edges_on_nodes[current_node.position]
                for edge in connected_boundary_edges:
                    if edge.edge_type == 'station <-> trajectory':
                        # Skip station <-> trajectory edges.
                        continue
                    elif edge.node1 == current_node:
                        connected_boundary_nodes.append([edge.node2, None, '2', edge])
                    else:
                        connected_boundary_nodes.append([edge.node1, None, '1', edge])
                # else:
                #    raise ValueError('No connected boundary edges found in definition of boundary nodes and edges.')

                # Calculate the relative angle between the current edge and each connected edge.
                # Replace the second entries of connected_boundary_nodes with the relative angles.
                for edge_index, connected_boundary_node in enumerate(connected_boundary_nodes):
                    if connected_boundary_node[3] == current_edge and current_edge is not None:
                        # Same edge. Angle is pi or -pi. Should be the least likely case.
                        if interior_boundary:
                            # Relative to the right.
                            connected_boundary_nodes[edge_index][1] = -math.pi
                        else:
                            # Relative to the left.
                            connected_boundary_nodes[edge_index][1] = math.pi
                        continue

                    # Determine the nodes of the connected (new) edge.
                    if connected_boundary_node[2] == '1':
                        new_edge_nodes = [connected_boundary_node[3].node2, connected_boundary_node[0]]
                    elif connected_boundary_node[2] == '2':
                        new_edge_nodes = [connected_boundary_node[3].node1, connected_boundary_node[0]]

                    if current_edge is not None:
                        # Determine the nodes of the current edge.
                        if current_edge.node1 in new_edge_nodes:
                            current_edge_nodes = [current_edge.node2, current_edge.node1]
                        elif current_edge.node2 in new_edge_nodes:
                            current_edge_nodes = [current_edge.node1, current_edge.node2]

                        # Calculate the relative angle between the current edge and the new edge.
                        relative_angle = self.calculate_angle(current_edge_nodes, new_edge_nodes)

                    else:
                        # First iteration. There is no current edge.
                        # Calculate the relative angle between the first segment of the boundary and each connected edge.
                        current_edge_nodes = [corner_nodes[0], corner_nodes[1]]

                        # Calculate the relative angle between the first segment of the boundary and the new edge.
                        relative_angle = self.calculate_angle(current_edge_nodes, new_edge_nodes, first_iteration=True)

                        # TODO: Hack: Edges pointing slightly to the right are prioritized, since a small factor is added (12,25 degrees).
                        # TODO: Find a better solution to define the first edge.
                        relative_angle += math.pi / 32

                    # Store the relative angle.
                    connected_boundary_nodes[edge_index][1] = relative_angle

                # Sort the connected boundary nodes by the relative angles of the edges.
                if interior_boundary and current_edge is not None:
                    # Interior boundary.
                    # Order the edges by the relative angle. The first edge is the one pointing the most to the left relatively.
                    connected_boundary_nodes.sort(key=lambda x: x[1], reverse=True)
                elif current_edge is not None:
                    # Exterior boundary.
                    # Order the edges by the relative angle. The first edge is the one pointing the most to the right relatively.
                    connected_boundary_nodes.sort(key=lambda x: x[1])
                else:
                    # First iteration, interior od exterior boundary.
                    # Order the edges by the relative angle. The first edge is the one with the smallest relative angle difference
                    # to the first segment of the boundary.
                    connected_boundary_nodes.sort(key=lambda x: abs(x[1]))

                # Update current node, current edge and visited nodes and edges.
                # Also check if edge has already been visited twice for that boundary.
                if len(connected_boundary_nodes) == 0:
                    raise ValueError('No connected boundary nodes found in definition of boundary nodes and edges. Node: '
                                     + str(current_node.position))
                current_edge = connected_boundary_nodes[0][3]
                if current_edge in visited_edges_boundary_twice:
                    raise ValueError('Error in definition of boundary nodes and edges. Edge visited the third time.')
                elif current_edge in visited_edges_boundary:
                    visited_edges_boundary_twice.append(current_edge)
                else:
                    visited_edges_boundary.append(current_edge)
                current_node = connected_boundary_nodes[0][0]

                # Add the current node and edge to the boundary nodes and edges.
                boundary_nodes.add(current_node)
                boundary_edges.add(current_edge)

                # Set node and edge as boundary.
                current_edge.boundary_edge = True
                current_node.boundary_node = True

        # Set all nodes and edges that are not boundary nodes and edges to non-boundary.
        for node in self.graph.nodes:
            if node not in boundary_nodes:
                node.boundary_node = False
        for edge in self.graph.edges:
            if edge not in boundary_edges:
                edge.boundary_edge = False

    def calculate_angle(self, edge1, edge2, first_iteration=False):
        """
        Calculate the angle between two edges.
        If the edge is pointing to the right relatively, the angle is negative.
        If the edge is pointing to the left relatively, the angle is positive.

        edge1: Current edge, ordered tuple of two nodes.
        edge2: New edge, ordered tuple of two nodes.
        """
        # Calculate the vectors of the edges.
        if first_iteration:
            vector1 = (edge1[1][0] - edge1[0][0], edge1[1][1] - edge1[0][1])
        else:
            vector1 = (edge1[1].position[0] - edge1[0].position[0], edge1[1].position[1] - edge1[0].position[1])
        vector2 = (edge2[1].position[0] - edge2[0].position[0], edge2[1].position[1] - edge2[0].position[1])

        # Calculate the angle of each vector.
        angle1 = math.atan2(vector1[1], vector1[0])
        angle2 = math.atan2(vector2[1], vector2[0])

        # Calculate the relative angle from vector1 to vector2.
        relative_angle = angle2 - angle1

        # Normalize the relative angle to the range [-pi, pi].
        relative_angle = (relative_angle + math.pi) % (2 * math.pi) - math.pi

        return relative_angle
