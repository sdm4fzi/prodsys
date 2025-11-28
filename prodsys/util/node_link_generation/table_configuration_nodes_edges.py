import math
import random
import numpy as np
import shapely
from scipy.spatial import Delaunay
from prodsys.util.node_link_generation.configuration import Configuration 
from prodsys.util.node_link_generation.graph import Graph


class NodeEdgeGenerator:
    def __init__(self, config, table_config, station_config):
        # Objects.
        self.config = config
        self.table_config = table_config
        self.station_config = station_config
        self.graph = Graph()

        # Boundary conditions.
        self.boundary_distance = config.get(Configuration.Boundary_Distance)
        self.required_node_clearance = config.get(Configuration.Min_Node_Distance)
        self.required_node_edge_clearance = config.get(Configuration.Min_Node_Edge_Distance)
        self.buffer_node_distance = config.get(Configuration.Buffer_Node_Distance)

    # ------------------------ Nodes ------------------------
    def get_station_nodes_in_cfree(self, buffer_nodes=True) -> tuple:
        """
        Definition of station trajectory nodes and station buffer nodes in cfree as shapely points.
        """
        station_nodes = []
        node_types = []
        for station in self.station_config.stations:
            # Station trajectory nodes.
            for station_trajectory_node in station.station_corner_nodes:
                point = shapely.Point(station_trajectory_node)
                if point.within(self.table_config.table_configuration_polygon_cfree):
                    station_nodes.append(point)
                    node_types.append('trajectory')

            # Station buffer nodes. (not used in prodsys)
            """if buffer_nodes:
                for buffer_node in station.station_buffer_nodes:
                    point = shapely.Point(buffer_node)
                    if point.within(self.table_config.table_configuration_polygon_cfree) \
                            and min(point.distance(station_nodes)) >= self.required_node_clearance:
                        station_nodes.append(point)
                        node_types.append('buffer')"""

        return station_nodes, node_types

    def add_station_nodes(self, station_nodes, node_types) -> None:
        """
        Add station nodes to the graph.

        :param station_nodes: List of station nodes as shapely points.
        :param node_types: List of node types. 'trajectory' or 'buffer'.
        """
        for station_node in station_nodes:
            #self.graph.add_node((station_node.x, station_node.y), station_node, node_types[station_nodes.index(station_node)],
            #                        boundary_node=True)
            if self.graph.nodes == []:
                self.graph.add_node((station_node.x, station_node.y), station_node, node_types[station_nodes.index(station_node)],
                                    boundary_node=True)
            elif min(station_node.distance(self.graph.node_points)) >= self.required_node_clearance \
                    and self.graph.edges_lines == []:
                self.graph.add_node((station_node.x, station_node.y), station_node, node_types[station_nodes.index(station_node)],
                                    boundary_node=True)
            elif min(station_node.distance(self.graph.node_points)) >= self.required_node_clearance \
                    and min(station_node.distance(self.graph.edges_lines) >= self.required_node_edge_clearance):
                self.graph.add_node((station_node.x, station_node.y), station_node, node_types[station_nodes.index(station_node)],
                                    boundary_node=True)
            #elif node_types[station_nodes.index(station_node)] == 'trajectory' and station_node not in self.graph.node_points:
            #    raise ValueError("Trajectory node can't be added: " + str(station_node))

    def add_corner_nodes(self, replace_buffer: bool = False, corner_nodes_list: list = []) -> None:
        """
        Add table configuration corner nodes to the graph. Should be done after station nodes are added.

        :param replace_buffer: If True, buffer nodes are replaced by convex corner nodes if they are too close to the corner nodes.
        :param corner_nodes_list: List of corner nodes. If None, all corner nodes are added. No order is defined.
        """
        if corner_nodes_list == []:
            convex_corner_nodes = []
            concave_corner_nodes = []
            for corner_nodes in self.table_config.table_configuration_corner_nodes_cfree:
                for corner_node in corner_nodes:
                    # Check if the node is a convex or a concave corner node.
                    corner_type = self.table_config.check_corner_type(corner_node)

                    if corner_type == 'convex':
                        # List of convex corner nodes.
                        convex_corner_nodes.append(corner_node)

                    elif corner_type == 'concave':
                        # List of concave corner nodes.
                        concave_corner_nodes.append(corner_node)

            # Convex corner nodes are added first. They are prioritized.
            corner_nodes_list = [*convex_corner_nodes, *concave_corner_nodes]

        for corner_node in corner_nodes_list:
            point = shapely.Point(corner_node)

            # Check if it is a convex or a concave corner node.
            corner_type = self.table_config.check_corner_type(corner_node)

            # Check if the node already exists in the graph. If yes, update the corner type of the node.
            if corner_node in self.graph.node_positions:
                node_index = self.graph.node_positions.index(corner_node)
                self.graph.nodes[node_index].corner_type = corner_type

            # Check if node has the required distance to other nodes (and edges) and is in cfree.
            elif min(point.distance(self.graph.node_points)) >= self.required_node_clearance:
                if self.graph.edges_lines == []:
                    self.graph.add_node(corner_node, point, corner_type=corner_type, boundary_node=True)

                elif min(point.distance(self.graph.edges_lines)) >= self.required_node_edge_clearance:
                    self.graph.add_node(corner_node, point, corner_type=corner_type, boundary_node=True)

            # Define corner node type and update buffer node position optionally.
            elif min(point.distance(self.graph.node_points)) < self.required_node_clearance:
                node_distances = point.distance(self.graph.node_points)
                too_close_node_indices = np.where(node_distances < self.required_node_clearance)[0]

                # Iterate through too close nodes and check if it is a buffer node. #TODO: Adapt this to not use buffer nodes, as it might result in errors
                for too_close_node_index in too_close_node_indices:
                    if self.graph.nodes[too_close_node_index].node_type == 'buffer':
                        if corner_type == 'convex' and replace_buffer and len(too_close_node_indices) == 1 \
                                and self.graph.nodes[too_close_node_index].position in self.station_config.station_buffer_nodes:
                            # Only one (buffer) node is too close. Replace buffer node by a convex corner node. A node can only be replaced once.
                            self.graph.update_node_position(self.graph.nodes[too_close_node_index].position, corner_node,
                                                            check_clearance=True, node_edge_generator=self)
                            # Update corner type of the node.
                            self.graph.nodes[too_close_node_index].corner_type = 'convex'

                        elif corner_type == 'convex' and replace_buffer \
                                and self.graph.nodes[too_close_node_index].position in self.station_config.station_buffer_nodes:
                            # More nodes are too close. Replace buffer node by a convex corner node. A node can only be replaced once.
                            nodes_to_remove = []
                            node_changeable = True
                            for too_close_node_index_2 in too_close_node_indices:
                                nodes_to_remove.append(self.graph.nodes[too_close_node_index_2])
                                if self.graph.nodes[too_close_node_index_2].node_type == 'trajectory' \
                                        or self.graph.nodes[too_close_node_index_2].corner_type == 'convex':
                                    node_changeable = False
                                    break

                            if node_changeable:
                                # Remove too close nodes.
                                for node_to_remove in nodes_to_remove:
                                    self.graph.remove_node(node_to_remove)

                                # Add convex corner node.
                                self.graph.add_node(corner_node, point, corner_type=corner_type, boundary_node=True)

                                # Update corner type of the node.
                                self.graph.nodes[too_close_node_index].corner_type = 'convex'
                                break

                            else:
                                # Buffer node can't be replaced by a convex corner node. Buffer node is a convex corner node.
                                self.graph.nodes[too_close_node_index].corner_type = 'convex'

                        elif corner_type == 'convex':
                            # Update corner type of the node.
                            self.graph.nodes[too_close_node_index].corner_type = 'convex'

                        elif corner_type == 'concave' and self.graph.nodes[too_close_node_index].corner_type != 'convex':
                            # Update corner type of the node if it is not already a convex corner node.
                            self.graph.nodes[too_close_node_index].corner_type = 'concave'

    def define_fixed_table_nodes(self) -> None:
        """
        Define nodes on predefined positions on the table modules. Station nodes must be added before.
        Function is used for testing purposes.
        """
        for table in self.table_config.tables:
            # Define nodes on predefined positions on the tables.
            table_nodes = self.table_config.define_table_nodes(table)

            # Add table nodes to the graph if they are in cfree and have the required distance to other nodes (and edges).
            for table_node in table_nodes:
                point = shapely.Point(table_node)
                if point.within(self.table_config.table_configuration_polygon_cfree) \
                        and min(point.distance(self.graph.node_points)) >= self.required_node_clearance:
                    if self.graph.edges_lines == []:
                        # No edges in the graph. Add node.
                        self.graph.add_node(table_node, point, boundary_node=True)
                    elif min(point.distance(self.graph.edges_lines)) >= self.required_node_edge_clearance:
                        # Clearance to edges is given. Add node.
                        self.graph.add_node(table_node, point, boundary_node=True)

    def define_random_nodes(self, min_node_distance=None) -> None:
        """
        Define random nodes in cfree.
        Station nodes must be added before.
        Outer nodes and edges of table configuration can be added before.
        """
        # Initialize.
        count = 0
        iterations = 0
        max_iterations = 10000
        min_x, min_y, max_x, max_y = self.table_config.table_configuration_polygon_cfree_round.bounds

        if min_node_distance is None or min_node_distance < self.required_node_clearance:
            min_node_distance = self.required_node_clearance

        while iterations < max_iterations:
            iterations += 1

            # Random node.
            random_node = (random.randint(int(min_x), int(max_x) + 1), random.randint(int(min_y), int(max_y) + 1))
            point = shapely.Point(random_node)

            # Check if node has the required distance to other nodes (and edges) and is in cfree.
            if min(point.distance(self.graph.node_points)) >= min_node_distance \
                    and point.within(self.table_config.table_configuration_polygon_cfree_round):
                if self.graph.edges_lines == []:
                    # No edges in the graph. Add node.
                    self.graph.add_node(random_node, point)
                    count += 1
                elif min(point.distance(self.graph.edges_lines)) >= self.required_node_edge_clearance:
                    # Clearance to edges is given. Add node.
                    self.graph.add_node(random_node, point)
                    count += 1

        #print(str(count) + " random nodes defined in cfree.")

    def define_local_grids(self, grid_spacing: int = 32) -> None:
        """
        Function defines local, equidistant grids in cfree around the table configuration corner nodes.
        Station nodes must be added before.
        """
        # TODO: Prioritize specific corner nodes?
        # Add table configuration corner nodes and generate a local grid around the nodes.
        convex_corner_nodes = []
        concave_corner_nodes = []
        for corner_nodes in self.table_config.table_configuration_corner_nodes_cfree:
            for corner_node in corner_nodes:
                # Check if the node is a convex or a concave corner node.
                corner_type = self.table_config.check_corner_type(corner_node)

                if corner_type == 'convex':
                    # List of convex corner nodes.
                    convex_corner_nodes.append(corner_node)

                elif corner_type == 'concave':
                    # List of concave corner nodes.
                    concave_corner_nodes.append(corner_node)

        # Add table configuration corner nodes. Convex corner nodes are added first.
        self.add_corner_nodes(replace_buffer=True, corner_nodes_list=[*convex_corner_nodes, *concave_corner_nodes])

        # TODO: Maximum minimal distance between corner nodes can be used to estimate the maximum range of the local grids.
        # Add local grids around the corner nodes. Increase the range of the local grid.
        max_range = 10  # 15
        for local_grid_range in [[1, 2], [3, 5], [6, max_range]]:
            # Convex corner nodes are considered first.
            for corner_node in [*convex_corner_nodes, *concave_corner_nodes]:
                # Calculate local grid nodes around the corner node.
                neighbor_nodes = self.get_neighbor_nodes(corner_node, node_distance=grid_spacing,
                                                         max_nodes=local_grid_range[1], min_nodes=local_grid_range[0])
                for neighbor_node in neighbor_nodes:
                    neighbor_point = shapely.Point(neighbor_node)

                    # Check if node has the required distance to other nodes (and edges) and is in cfree.
                    if neighbor_point.within(self.table_config.table_configuration_polygon_cfree) \
                            and min(neighbor_point.distance(self.graph.node_points) >= self.required_node_clearance):
                        if self.graph.edges_lines == []:
                            # No edges in the graph. Add node.
                            self.graph.add_node(neighbor_node, neighbor_point)

                        elif min(neighbor_point.distance(self.graph.edges_lines)) >= self.required_node_edge_clearance:
                            # Clearance to edges is given. Add node.
                            self.graph.add_node(neighbor_node, neighbor_point)

    def define_global_grid(self, grid_spacing: int, adjust_spacing: bool = False, add_corner_nodes_first: bool = True) -> None:
        """
        Function defines a global, equidistant grid in cfree.
        Station nodes must be added before.
        Problem: It cannot be guaranteed that a connected graph is generated.
                 As a solution corner nodes can be added first and be prioritized (replace_buffer=True).

        :param grid_spacing: Spacing of the grid. Should be equal or larger than the required node clearance.
        :param adjust_spacing: If True, the grid spacing is adjusted to the table module size automatically.
        :param add_corner_nodes_first: If True, corner nodes are added first to ensure that a connected graph can be generated.
        """
        # Define boundaries of the grid.
        x_min = round(self.table_config.table_configuration_polygon.bounds[0]) + self.boundary_distance  # grid_spacing/2
        y_min = round(self.table_config.table_configuration_polygon.bounds[1]) + self.boundary_distance  # grid_spacing/2
        x_max = round(self.table_config.table_configuration_polygon.bounds[2]) - self.boundary_distance  # grid_spacing/2
        y_max = round(self.table_config.table_configuration_polygon.bounds[3]) - self.boundary_distance  # grid_spacing/2

        if add_corner_nodes_first:
            # Add corner nodes first to ensure that a connected graph can be generated. Buffer nodes can be replaced.
            self.add_corner_nodes(replace_buffer=True)

        # Adjust grid spacing to table module size.
        if adjust_spacing:
            if grid_spacing < 34:
                grid_spacing = 33 + 1/3
            elif grid_spacing >= 34 and grid_spacing <= 50:
                grid_spacing = 50
            else:
                pass

        # Define grid.
        for x in np.arange(x_min, x_max + 1, grid_spacing):
            # if x > 550:
            #     x += 20
            for y in np.arange(y_min, y_max + 1, grid_spacing):
                # if y > 550:
                #     y += 20
                node = (round(x), round(y))
                point = shapely.Point(node)

                # Check if node has the required distance to other nodes (and edges) and is in cfree.
                if point.within(self.table_config.table_configuration_polygon_cfree) \
                        and min(point.distance(self.graph.node_points)) >= self.required_node_clearance:

                    if self.graph.edges_lines == []:
                        # No edges in the graph. Add node.
                        self.graph.add_node(node, point)

                    elif min(point.distance(self.graph.edges_lines)) >= self.required_node_edge_clearance:
                        # Clearance to edges is given. Add node.
                        self.graph.add_node(node, point)

    def define_nodes_based_on_grid(self, grid_spacing: int, add_corner_nodes_first: bool = True) -> None:
        """
        Function defines nodes in cfree based on a grid defined by the grid spacing.
        Station nodes must be added before.
        Problem: It cannot be guaranteed that a connected graph is generated.
                 As a solution corner nodes can be added first and be prioritized (replace_buffer=True).

        :param grid_spacing: Spacing of the grid. Can be smaller than the required node clearance.
        :param add_corner_nodes_first: If True, corner nodes are added first to ensure that a connected graph can be generated.
        """
        # Define boundaries of the grid.
        x_min = round(self.table_config.table_configuration_polygon.bounds[0]) + self.boundary_distance
        y_min = round(self.table_config.table_configuration_polygon.bounds[1]) + self.boundary_distance
        x_max = round(self.table_config.table_configuration_polygon.bounds[2]) - self.boundary_distance
        y_max = round(self.table_config.table_configuration_polygon.bounds[3]) - self.boundary_distance

        if add_corner_nodes_first:
            # Add corner nodes first to ensure that a connected graph can be generated. Buffer nodes can be replaced.
            self.add_corner_nodes(replace_buffer=True)

        # Define nodes based on a grid search.
        for x in range(x_min, x_max + 1, grid_spacing):
            for y in range(y_min, y_max + 1, grid_spacing):
                node = (x, y)
                point = shapely.Point(node)

                # Check if node has the required distance to other nodes (and edges) and is in cfree.
                if point.within(self.table_config.table_configuration_polygon_cfree) \
                        and min(point.distance(self.graph.node_points)) >= self.required_node_clearance:
                    # Search for neighbor nodes.
                    neighbor_nodes = self.get_neighbor_nodes(node, node_distance=self.required_node_clearance, max_nodes=4, min_nodes=1)
                    neighbor_points_to_add = []
                    for neighbor_node in neighbor_nodes:
                        neighbor_point = shapely.Point(neighbor_node)
                        if neighbor_point.within(self.table_config.table_configuration_polygon_cfree) \
                                and min(neighbor_point.distance(self.graph.node_points)) >= self.required_node_clearance \
                                and self.graph.edges_lines == []:
                            neighbor_points_to_add.append(neighbor_point)

                        elif neighbor_point.within(self.table_config.table_configuration_polygon_cfree) \
                                and min(neighbor_point.distance(self.graph.node_points)) >= self.required_node_clearance \
                                and min(neighbor_point.distance(self.graph.edges_lines)) >= self.required_node_edge_clearance:
                            neighbor_points_to_add.append(neighbor_point)

                    if self.graph.edges_lines == []:
                        if len(neighbor_points_to_add) > 0:
                            self.graph.add_node(node, point)
                            for neighbor_point in neighbor_points_to_add:
                                self.graph.add_node((neighbor_point.x, neighbor_point.y), neighbor_point)
                        # else:
                        #     self.graph.add_node(node, point)

                    elif min(point.distance(self.graph.edges_lines)) >= self.required_node_edge_clearance:
                        if len(neighbor_points_to_add) > 0:
                            self.graph.add_node(node, point)
                            for neighbor_point in neighbor_points_to_add:
                                self.graph.add_node((neighbor_point.x, neighbor_point.y), neighbor_point)
                        # else:
                        #     self.graph.add_node(node, point)

    def get_neighbor_nodes(self, coordinate, node_distance, max_nodes=10, min_nodes=0) -> list:
        """
        min_nodes and max_nodes are included.
        """
        neighbor_nodes = []

        range_limit = max_nodes
        step_size = 1

        for x in range(-range_limit, range_limit + 1, step_size):
            for y in range(-range_limit, range_limit + 1, step_size):
                if min_nodes == 0 and (not (- max_nodes <= x <= max_nodes) or not (- max_nodes <= y <= max_nodes)):
                    continue

                elif min_nodes != 0 and ((not (- max_nodes <= x <= max_nodes) or not (- max_nodes <= y <= max_nodes))
                                         or ((- min_nodes < x < min_nodes) and (- min_nodes < y < min_nodes))):
                    continue

                neighbor_nodes.append((coordinate[0] + node_distance * x, coordinate[1] + node_distance * y))

        return neighbor_nodes

    def get_nodes_in_between(self, node_1, node_2, node_distance, right_and_left_variance=0, int_type=True) -> list:
        """
        Calculating intermediate nodes in between the two given nodes.
        node_distance: Distance between the intermediate nodes.
        right_and_left_variance: If 0, the nodes are positioned on the straight connection.
                                 If not 0, the nodes are positioned at a distance of right_and_left_variance perpendicular
                                    to the nodes on the straight connection.
        int_type: If True, node positions are of type int. Otherwise positions are of type float.
        return: List of intermediate nodes between the two given nodes. node_1 and node_2 are excluded.
        """
        nodes_in_between = []

        if right_and_left_variance != 0:
            if node_1[0] == node_2[0]:
                vary_coordinate = "x"
            elif node_1[1] == node_2[1]:
                vary_coordinate = "y"

        distance = math.dist(node_1, node_2)
        nodes_count = math.floor(distance / node_distance)
        for i in range(nodes_count):
            if i == 0:
                continue
            if int_type:
                node_x = int(node_1[0] + (node_2[0] - node_1[0]) * i / nodes_count)
                node_y = int(node_1[1] + (node_2[1] - node_1[1]) * i / nodes_count)
            else:
                node_x = node_1[0] + (node_2[0] - node_1[0]) * i / nodes_count
                node_y = node_1[1] + (node_2[1] - node_1[1]) * i / nodes_count
            if right_and_left_variance != 0:
                if vary_coordinate == "x":
                    nodes_in_between.append((node_x + right_and_left_variance, node_y))
                    nodes_in_between.append((node_x - right_and_left_variance, node_y))
                elif vary_coordinate == "y":
                    nodes_in_between.append((node_x, node_y + right_and_left_variance))
                    nodes_in_between.append((node_x, node_y - right_and_left_variance))
            else:
                nodes_in_between.append((node_x, node_y))

        return nodes_in_between

    # ------------------------ Nodes and Edges ------------------------
    def add_station_nodes_and_edges(self, add_edges=False, buffer_nodes=True) -> None:
        """
        Function adds station nodes and edges to the graph.
        add_edges: If True, edges are added between the nodes of a station.
        """
        # Add station nodes.
        station_nodes, node_types = self.get_station_nodes_in_cfree(buffer_nodes)
        self.add_station_nodes(station_nodes, node_types)

        # Connect station nodes by edges.
        if add_edges:
            self.connect_station_trajectory_to_station_buffer_nodes()

    def add_outer_nodes_and_edges(self, edge_directionality, add_nodes_between=False, max_node_distance=64, min_node_distance=32,
                                    add_edges=False) -> None:
        """
        Function adds nodes along the outer (exterior and interior) edges of the table configuration to the graph.
        Corner nodes of the table configuration are the basis nodes. Station nodes must be added before.
        Intermediate nodes along the edges can be added. Edges can be added between the nodes.

        edge_directionality: Object of the class EdgeDirectionality.
        add_nodes_between: If True, intermediate nodes along the edges are added if it is possible.
        max_node_distance: If distance between basis nodes is larger max_node_distance, intermediate nodes are added.
        min_node_distance: Minimal distance between intermediate nodes.
        add_edges: If True, edges are added between the nodes.
        """
        # Hack: Buffer node positions are only optimized, if add_edges is True.
        # Set add_edges to True and remove edges afterwards.
        if add_edges:
            remove_edges = False
        else:
            add_edges = True
            remove_edges = True

        # Add station nodes and edges.
        self.add_station_nodes_and_edges(add_edges=add_edges)

        # Add table configuration corner nodes for exterior an interior edges.
        outer_boundaries_count = len(self.table_config.table_configuration_corner_nodes_cfree)
        for boundary_index in range(outer_boundaries_count):
            previous_node = None
            corner_nodes = self.table_config.table_configuration_corner_nodes_cfree[boundary_index]
            for index, corner_node in enumerate(corner_nodes):
                if index == len(corner_nodes) - 1:
                    # Last corner node. Connect with the first corner node.
                    previous_node = self.add_corner_nodes_and_edges(corner_node, corner_nodes[0], min_node_distance,
                                                                    add_edges=add_edges, previous_node=previous_node,
                                                                    boundary_index=boundary_index)
                    continue

                # Add corner nodes and edges.
                previous_node = self.add_corner_nodes_and_edges(corner_node, corner_nodes[index + 1],
                                                                min_node_distance, add_edges=add_edges,
                                                                previous_node=previous_node, boundary_index=boundary_index)

        if min_node_distance > 50 or not add_nodes_between: #TODO: adapt the 50 to be dynamically adjusted
            # Adjust minimum node distance between intermediate nodes.
            # add_corner_nodes_and_edges is only working properly, if node distance is not too large.
            self.remove_intermediate_outer_nodes(edge_directionality, min_node_distance=min_node_distance,
                                                 add_nodes_between=add_nodes_between)

        if remove_edges:
            # Remove edges.
            self.graph.remove_all_nodes_and_edges(nodes=False, edges=True)

        # Define type of corner nodes. replace_buffer must be False.
        self.add_corner_nodes(replace_buffer=False)

    def add_corner_nodes_and_edges(self, node_1, node_2, min_node_distance, add_edges=False,
                                   previous_node=None, boundary_index=None) -> object:
        """
        Function adds the two given corner nodes to the graph, if the node clearance is given.
        node_1: First corner node.
        node_2: Second corner node.
        min_node_distance: Minimal distance between intermediate nodes.
        add_edges: If True, edges between the nodes are added.
        previous_node: Previous node. If add_edges is True, edge between the previous node and node_1 is added.
        boundary_index: Index of the boundary.
        """
        nodes_to_add = []
        current_node = None

        # Add first corner node.
        nodes_to_add.append(node_1)

        # Add nodes in between the corner nodes.
        if min_node_distance < self.required_node_clearance:
            # Adjust the minimal node distance to the required node clearance.
            min_node_distance = self.required_node_clearance

        # TODO: Algorithm is not working properly if min_node_distance is too large. Restrict min_node_distance.
        elif min_node_distance > 50:
            # Adjust the minimal node distance to a range between the required node clearance and 50.
            # A variable value is used to be able to better adjust the minimal node distance later in remove_intermediate_outer_nodes.
            divider = min_node_distance // self.required_node_clearance
            min_node_distance = math.ceil(min_node_distance / divider)
            if min_node_distance > 50:
                min_node_distance = 50

        # Calculate intermediate nodes in between the corner nodes and add them to nodes_to_add.
        # This is also done, if add_edges is False. Intermediate nodes are removed afterwards in remove_intermediate_outer_nodes.
        nodes_in_between = self.get_nodes_in_between(node_1, node_2, min_node_distance)
        nodes_to_add.extend(nodes_in_between)

        # Add second corner node.
        nodes_to_add.append(node_2)

        for node_index, node_to_add in enumerate(nodes_to_add):
            edge_added = False
            point_to_add = shapely.Point(node_to_add)
            if point_to_add.within(self.table_config.table_configuration_polygon_cfree_round):
                # Check if node has already been added.
                if point_to_add in self.graph.node_points:
                    current_node = self.graph.nodes[self.graph.node_points.index(point_to_add)]

                # Check if node has the required distance to other nodes (and edges).
                elif min(point_to_add.distance(self.graph.node_points)) >= self.required_node_clearance \
                        and self.graph.edges_lines == []:
                    # Add node.
                    self.graph.add_node(node_to_add, point_to_add, boundary_node=True)
                    current_node = self.graph.nodes[-1]
                elif min(point_to_add.distance(self.graph.node_points)) >= self.required_node_clearance \
                        and min(point_to_add.distance(self.graph.edges_lines)) >= self.required_node_edge_clearance:
                    # Add node.
                    self.graph.add_node(node_to_add, point_to_add, boundary_node=True)
                    current_node = self.graph.nodes[-1]

                # Node(s) too close. Define current_node.
                elif min(point_to_add.distance(self.graph.node_points)) < self.required_node_clearance:
                    # Find nodes that are too close.
                    node_distances = point_to_add.distance(self.graph.node_points)
                    too_close_node_indices = np.where(node_distances < self.required_node_clearance)[0]
                    closest_node_index = point_to_add.distance(self.graph.node_points).argmin()

                    # Find closest node to the previous node of the found too close nodes.
                    if previous_node is not None:
                        if len(too_close_node_indices) == 1:
                            # Only one node is too close.
                            if node_to_add in self.table_config.table_configuration_corner_nodes_cfree[boundary_index] \
                                    and not (self.graph.nodes[too_close_node_indices[0]].node_type == 'station'
                                             or self.graph.nodes[too_close_node_indices[0]].node_type == 'trajectory'
                                             # or self.graph.nodes[too_close_node_indices[0]].node_type == 'buffer'
                                             or self.graph.nodes[too_close_node_indices[0]].position
                                             in self.table_config.table_configuration_corner_nodes_cfree[boundary_index]):
                                if self.graph.nodes[too_close_node_indices[0]].node_type == 'buffer' \
                                        and not (node_to_add == node_1 or node_to_add == node_2):
                                    pass  # Intermediate nodes can't replace a buffer node.
                                else:
                                    # Replace node.
                                    self.graph.update_node_position(self.graph.nodes[too_close_node_indices[0]].position, node_to_add,
                                                                    check_clearance=True, node_edge_generator=self)
                                    current_node = self.graph.nodes[too_close_node_indices[0]]
                            else:
                                current_node = self.graph.nodes[too_close_node_indices[0]]

                        else:
                            # More than one node is too close.
                            for too_close_node_index in too_close_node_indices:
                                current_node = self.graph.nodes[too_close_node_index]

                                # Try to connect the nodes by an edge.
                                if add_edges and current_node is not None and previous_node is not None \
                                        and current_node is not previous_node:
                                    line = shapely.LineString([current_node.position, previous_node.position])
                                    line_clearance, _ = self.check_line_clearance(current_node.position, previous_node.position, line)
                                    if line_clearance:
                                        # Connect the nodes by edges.
                                        self.graph.add_edge(current_node, previous_node, line, boundary_edge=True)
                                        edge_added = True
                                        continue

                                if add_edges:
                                    # Try to connect buffer node.
                                    if current_node.node_type == 'buffer' and len(self.graph.edges_on_nodes[current_node.position]) == 1 \
                                            and len(self.graph.edges_on_nodes[previous_node.position]) == 1 \
                                            and current_node is not previous_node:

                                        return_node = self.try_to_connect_buffer_node(other_node=previous_node,
                                                                                      initial_buffer_node=current_node)
                                        if return_node is not None:
                                            current_node = return_node
                                            continue

                    else:
                        # At the beginning, the current node is set to the closest node, if the node has not the required node clearance.
                        current_node = self.graph.nodes[closest_node_index]

                # Try to connect the nodes by an edge.
                if add_edges and current_node is not None and previous_node is not None and current_node is not previous_node \
                        and not edge_added:
                    line = shapely.LineString([current_node.position, previous_node.position])
                    line_clearance, _ = self.check_line_clearance(current_node.position, previous_node.position, line)
                    if line_clearance:
                        # Connect the nodes by edges.
                        self.graph.add_edge(current_node, previous_node, line, boundary_edge=True)
                        edge_added = True

                    elif previous_node.position in self.graph.edges_on_nodes.keys():
                        # Check, if edge to direct neighbors of previous nodes is possible.
                        connected_edges = self.graph.edges_on_nodes[previous_node.position]
                        for connected_edge in connected_edges:
                            neighbor_node = None
                            if connected_edge.node1 == previous_node and connected_edge.node2 != current_node:
                                neighbor_node = connected_edge.node2
                            elif connected_edge.node2 == previous_node and connected_edge.node1 != current_node:
                                neighbor_node = connected_edge.node1

                            if neighbor_node is not None:
                                line = shapely.LineString([current_node.position, neighbor_node.position])
                                line_clearance, _ = self.check_line_clearance(current_node.position, neighbor_node.position, line)
                                if line_clearance and line.length < 1.5 * min_node_distance:
                                    # Connect the nodes by edges. Maximum length of the line is restricted.
                                    self.graph.add_edge(current_node, neighbor_node, line, boundary_edge=True)
                                    edge_added = True
                                    break

                    # Try to connect buffer node.
                    if not edge_added and \
                            (previous_node.node_type == 'buffer'
                             and len(self.graph.edges_on_nodes[previous_node.position]) == 1) \
                            and current_node is not previous_node:

                        self.try_to_connect_buffer_node(other_node=current_node, initial_buffer_node=previous_node)

                # Update previous node.
                previous_node = current_node

            else:
                raise ValueError("Node is out of table configuration.")

        return previous_node

    def remove_intermediate_outer_nodes(self, edge_directionality, min_node_distance, add_nodes_between=False) -> None:
        """
        Function removes intermediate nodes that are too close to other connected nodes.
        """
        if not add_nodes_between:
            # All intermediate nodes should be removed. Set min_node_distance to an arbitrary large value.
            min_node_distance = 100000000
        for boundary_index, corner_nodes in enumerate(self.table_config.table_configuration_corner_nodes_cfree):
            # Reset.
            current_node = None
            previous_node = None
            current_edge = None

            if boundary_index != 0:
                # Interior boundary. Direction of exterior and interior boundary should be different.
                interior_boundary = True

            else:
                # Exterior boundary.
                interior_boundary = False

            # Lower left node is the origin node.
            origin_node_position = corner_nodes[0]

            # Find the closest node of the boundary nodes to the origin node. This node is the start node.
            node_distances = [math.dist(origin_node_position, node.position) for node in self.graph.nodes]
            min_index = node_distances.index(min(node_distances))
            start_node = self.graph.nodes[min_index]

            # Remove intermediate nodes that are too close to other nodes.
            while current_node != start_node:
                # List, [node, relative angle, position of node in edge, edge].
                connected_boundary_nodes = []

                if current_node is None:
                    # First iteration.
                    current_node = start_node

                # Find the edges that are connected to the current node.
                if current_node.position in self.graph.edges_on_nodes.keys():
                    connected_boundary_edges = self.graph.edges_on_nodes[current_node.position]
                    for edge in connected_boundary_edges:
                        if edge.edge_type == 'station <-> trajectory':
                            # Skip station <-> trajectory edges.
                            continue
                        elif edge.node1 == current_node:
                            connected_boundary_nodes.append([edge.node2, None, '2', edge])
                        else:
                            connected_boundary_nodes.append([edge.node1, None, '1', edge])
                else:
                    raise ValueError('No connected boundary edges found.')

                # Calculate the relative angle between the current edge and the two connected edges.
                # Replace the second entries of connected_boundary_nodes with the relative angle.
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
                        relative_angle = edge_directionality.calculate_angle(current_edge_nodes, new_edge_nodes)

                    else:
                        # First iteration. There is no current edge.
                        # Calculate the relative angle between the first segment of the boundary and each connected edge.
                        current_edge_nodes = [corner_nodes[0], corner_nodes[1]]

                        # Calculate the relative angle between the first segment of the boundary and the new edge.
                        relative_angle = edge_directionality.calculate_angle(current_edge_nodes, new_edge_nodes, first_iteration=True)

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
                    raise ValueError('No connected boundary nodes found.')

                # Check if node is an intermediate node, if node distance is too small and if relative angle between edges is small.
                elif len(connected_boundary_nodes) == 2 and previous_node is not None \
                        and connected_boundary_nodes[0][3].shapely_line.length < min_node_distance \
                        and abs(connected_boundary_nodes[0][1]) < math.pi / 4 \
                        and not (current_node.node_type == 'station'
                                 or current_node.node_type == 'trajectory'
                                 or current_node.node_type == 'buffer'
                                 or current_node.position
                                 in self.table_config.table_configuration_corner_nodes_cfree[boundary_index]):
                    # Check if edge can be removed.
                    line = shapely.LineString([previous_node.position, connected_boundary_nodes[0][0].position])
                    line_clearance, _ = self.check_line_clearance_without(previous_node, connected_boundary_nodes[0][0], line,
                                                                          current_node, current_edge, connected_boundary_nodes[0][3])
                    if line_clearance:
                        # Remove intermediate node.
                        self.graph.remove_node(current_node)

                        # Add edge connection.
                        self.graph.add_edge(previous_node, connected_boundary_nodes[0][0], line, boundary_edge=True)

                        # Update current node and edge.
                        current_node = connected_boundary_nodes[0][0]
                        current_edge = self.graph.edges[-1]

                        if add_nodes_between and line.length > min_node_distance:
                            # Previous node is set to None.
                            previous_node = None

                    else:
                        # Update current node and edge as well as previous node.
                        previous_node = current_node
                        current_node = connected_boundary_nodes[0][0]
                        current_edge = connected_boundary_nodes[0][3]

                else:
                    # Update current node and edge as well as previous node.
                    previous_node = current_node
                    current_node = connected_boundary_nodes[0][0]
                    current_edge = connected_boundary_nodes[0][3]

    def add_medial_axis_nodes_and_edges(self, add_nodes_between=False, max_node_distance=64, min_node_distance=32,
                                        add_edges=True) -> None:
        """
        Function adds medial axis nodes and edges to the graph. Station nodes must be added before.
        Outer nodes and edges of table configuration can be added before.

        add_nodes_between: If True, intermediate nodes between the two nodes are added.
        max_node_distance: If distance between basis nodes is larger max_node_distance, intermediate nodes are added.
        min_node_distance: Minimal distance between intermediate nodes.
        add_edges: If True, edges are added between the nodes.
        """
        initial_nodes_dict = {}
        for index, medial_axis_edge in enumerate(self.table_config.medial_axis_edges):
            initial_nodes_dict = self.add_medial_axis_nodes_with_intermediate_nodes_and_edges(medial_axis_edge[0], medial_axis_edge[1],
                                                                                              min_node_distance,
                                                                                              initial_nodes_dict,
                                                                                              add_nodes_between=add_nodes_between,
                                                                                              add_edges=add_edges)

    def add_medial_axis_nodes_with_intermediate_nodes_and_edges(self, node_1, node_2, node_distance,
                                                                initial_nodes_dict,
                                                                add_nodes_between=False, add_edges=False) -> None:
        # TODO: Edge connections are not optimal.
        nodes_to_add = []
        current_node = None
        previous_node = None

        # Add first medial axis node.
        nodes_to_add.append((int(node_1[0]), int(node_1[1])))

        # Add nodes in between the medial axis nodes.
        if add_nodes_between:
            nodes_in_between = self.get_nodes_in_between(node_1, node_2, node_distance)
            nodes_to_add.extend(nodes_in_between)

        # Add second medial axis node.
        nodes_to_add.append((int(node_2[0]), int(node_2[1])))

        for node_index, node_to_add in enumerate(nodes_to_add):
            point_to_add = shapely.Point(node_to_add)
            if point_to_add.within(self.table_config.table_configuration_polygon_cfree_round):
                # Check node has already been added. Position equals a medial axis node.
                if point_to_add in self.graph.node_points:
                    current_node = self.graph.nodes[self.graph.node_points.index(point_to_add)]

                # Check node has already been added. Position of medial axis node has been changed.
                elif node_to_add in initial_nodes_dict.keys():
                    current_node = initial_nodes_dict[node_to_add]

                # Check if node has the required distance to other nodes (and edges).
                elif min(point_to_add.distance(self.graph.node_points)) >= self.required_node_clearance \
                        and self.graph.edges_lines == []:
                    # Add node.
                    self.graph.add_node(node_to_add, point_to_add)
                    current_node = self.graph.nodes[-1]
                elif min(point_to_add.distance(self.graph.node_points)) >= self.required_node_clearance \
                        and min(point_to_add.distance(self.graph.edges_lines)) >= self.required_node_edge_clearance:
                    # Add node.
                    self.graph.add_node(node_to_add, point_to_add)
                    current_node = self.graph.nodes[-1]

                # Node(s) (or edge(s)) too close. Try to move the node slightly.
                else:
                    if add_edges and (min(point_to_add.distance(self.graph.node_points)) < self.required_node_clearance
                                      or min(point_to_add.distance(self.graph.edges_lines)) < self.required_node_edge_clearance):
                        initial_node = node_to_add
                        node_to_add, point_to_add = self.try_to_move_node_slightly(node_to_add, add_edges=add_edges)
                        if node_to_add is None:
                            # No node position with required clearance found.
                            if previous_node is not None and initial_node not in initial_nodes_dict.keys():
                                # Add previous node to initial nodes dictionary. Helps to find edge connections.
                                initial_nodes_dict[initial_node] = previous_node
                        else:
                            # Add node and update initial nodes dictionary.
                            self.graph.add_node(node_to_add, point_to_add)
                            current_node = self.graph.nodes[-1]
                            initial_nodes_dict[initial_node] = current_node
                    elif min(point_to_add.distance(self.graph.node_points)) < self.required_node_clearance:
                        initial_node = node_to_add
                        node_to_add, point_to_add = self.try_to_move_node_slightly(node_to_add, add_edges=add_edges)
                        if node_to_add is None:
                            # No node position with required clearance found.
                            if previous_node is not None and initial_node not in initial_nodes_dict.keys():
                                # Add previous node to initial nodes dictionary. Helps to find edge connections.
                                initial_nodes_dict[initial_node] = previous_node
                        else:
                            # Add node and update initial nodes dictionary.
                            self.graph.add_node(node_to_add, point_to_add)
                            current_node = self.graph.nodes[-1]
                            initial_nodes_dict[initial_node] = current_node

                # Try to connect the nodes by an edge.
                if add_edges and current_node is not None and previous_node is not None and current_node is not previous_node:
                    line = shapely.LineString([current_node.position, previous_node.position])
                    line_clearance, _ = self.check_line_clearance(current_node.position, previous_node.position, line)
                    if line_clearance:
                        # Connect the nodes by edges.
                        self.graph.add_edge(current_node, previous_node, line)

                # Update previous node.
                previous_node = current_node

            else:
                raise ValueError("Node is out of table configuration.")

        return initial_nodes_dict

    def layout_calibration_network(self) -> None:
        """
        Function defines a node and edge network for calibration of the table configuration.
        """
        for table in self.table_config.tables:
            # Add table middle node.
            table_middle = (table.table_polygon.centroid.x, table.table_polygon.centroid.y)
            self.graph.add_node(table_middle, shapely.Point(table_middle), 'table middle node')
            table_middle_node = self.graph.nodes[-1]
            for calibration_node in table.table_configuration_intersection_middle_offset_nodes:
                point = shapely.Point(calibration_node)
                # Add table configuration intersection middle offset node.
                self.graph.add_node(calibration_node, point, 'table middle intersection offset node')
                # Add edge between table middle node and table configuration intersection middle offset node.
                table_middle_intersection_offset_node = self.graph.nodes[-1]
                self.graph.add_edge(table_middle_node, table_middle_intersection_offset_node,
                                    shapely.LineString([table_middle, calibration_node]))

        for calibration_node in self.table_config.table_configuration_intersection_middle_nodes:
            # Define table configuration intersection middle shapely point.
            point = shapely.Point(calibration_node)

            # Connect table configuration intersection middle node to closest table configuration intersection middle offset node(s).
            distance_nodes = [point.distance(node) for node in self.graph.node_points]
            minimal_distance = min(distance_nodes)
            # Find the indices of the elements with the minimal distance.
            indices_minimal_distance = [index for index, value in enumerate(distance_nodes) if value == minimal_distance]
            # Access the closest nodes.
            table_middle_intersection_offset_nodes = [self.graph.nodes[index] for index in indices_minimal_distance]

            # Add table configuration intersection middle node.
            self.graph.add_node(calibration_node, point, 'table middle intersection node')
            table_middle_intersection_node = self.graph.nodes[-1]

            for table_middle_intersection_offset_node in table_middle_intersection_offset_nodes:
                # Add edge between table configuration intersection middle node and table configuration intersection middle offset node
                self.graph.add_edge(table_middle_intersection_offset_node, table_middle_intersection_node,
                                    shapely.geometry.LineString([table_middle_intersection_offset_node.position, calibration_node]))

    def remove_nodes_with_1_edge(self) -> None:
        """
        Remove nodes with 1 edge. Station nodes can't be removed.
        """
        # Create a dictionary where the keys are the node positions and the values are the number of connections for each node.
        number_of_node_connections_per_node = {key: [len(value), value] for key, value in self.graph.edges_on_nodes.items()}

        # Find node objects with 1 or 2 edges.
        nodes_with_1_edge = []
        edges_connected_to_nodes_with_1_edge = []
        nodes_with_2_edges = []
        edges_connected_to_nodes_with_2_edges = []
        for key, value in number_of_node_connections_per_node.items():
            if value[0] == 1:
                if key == value[1][0].node1.position:
                    nodes_with_1_edge.append(value[1][0].node1)
                    edges_connected_to_nodes_with_1_edge.append(value[1])
                elif key == value[1][0].node2.position:
                    nodes_with_1_edge.append(value[1][0].node2)
                    edges_connected_to_nodes_with_1_edge.append(value[1])
            elif value[0] == 2:
                if key == value[1][0].node1.position:
                    nodes_with_2_edges.append(value[1][0].node1)
                    edges_connected_to_nodes_with_2_edges.append(value[1])
                elif key == value[1][0].node2.position:
                    nodes_with_2_edges.append(value[1][0].node2)
                    edges_connected_to_nodes_with_2_edges.append(value[1])

        # Remove nodes.
        for index_1, node in enumerate(nodes_with_1_edge):
            if node.node_type == 'station' or node.node_type == 'trajectory':
                # Station nodes can't be removed.
                continue

            edge = edges_connected_to_nodes_with_1_edge[index_1][0]
            # Find the second node, which is connected to the edge.
            if edge.node1 == node:
                connected_node = edge.node2
            elif edge.node2 == node:
                connected_node = edge.node1

            # Remove the node.
            self.graph.remove_node(node)

            # Check if the connected node has 1 or 2 edges.
            while connected_node in nodes_with_1_edge or connected_node in nodes_with_2_edges:
                if connected_node in nodes_with_1_edge:
                    self.graph.remove_node(node)
                    raise ValueError("Last node was removed.")

                elif connected_node in nodes_with_2_edges:
                    # Node is now connected to only one edge.
                    index_2 = nodes_with_2_edges.index(connected_node)
                    nodes_with_2_edges.pop(index_2)
                    edges_connected_to_nodes_with_2_edges.pop(index_2)
                    if connected_node.node_type == 'station':
                        # Station nodes can't be removed.
                        continue
                    elif connected_node.node_type == 'trajectory':
                        # Station trajectory nodes can't be removed.
                        continue

                    # Find the remaining edge, which is connected to the connected node.
                    connected_edge = self.graph.edges_on_nodes[connected_node.position][0]

                    # Remove the connected node.
                    self.graph.remove_node(connected_node)

                    # Find the second node, which is connected to the connected edge.
                    if connected_edge.node1 == connected_node:
                        connected_node = connected_edge.node2
                    elif connected_edge.node2 == connected_node:
                        connected_node = connected_edge.node1

    def remove_nodes_with_2_edges(self) -> None:
        """
        Remove nodes with 2 edges. Station nodes can't be removed.
        It must be possible to connect affected nodes with a straight edge in free space, otherwise the node cannot be removed.
        """
        # Create a dictionary where the keys are the node positions and the values are the number of connections for each node.
        number_of_node_connections_per_node = {key: [len(value), value] for key, value in self.graph.edges_on_nodes.items()}

        # Find node objects with 1 or 2 edges.
        nodes_with_1_edge = []
        edges_connected_to_nodes_with_1_edge = []
        nodes_with_2_edges = []
        edges_connected_to_nodes_with_2_edges = []
        for key, value in number_of_node_connections_per_node.items():
            if value[0] == 1:
                if key == value[1][0].node1.position:
                    nodes_with_1_edge.append(value[1][0].node1)
                    edges_connected_to_nodes_with_1_edge.append(value[1])
                elif key == value[1][0].node2.position:
                    nodes_with_1_edge.append(value[1][0].node2)
                    edges_connected_to_nodes_with_1_edge.append(value[1])
            elif value[0] == 2:
                if key == value[1][0].node1.position:
                    nodes_with_2_edges.append(value[1][0].node1)
                    edges_connected_to_nodes_with_2_edges.append(value[1])
                elif key == value[1][0].node2.position:
                    nodes_with_2_edges.append(value[1][0].node2)
                    edges_connected_to_nodes_with_2_edges.append(value[1])

        # Remove nodes with 2 edges.
        removed_nodes = []
        for index_1, node in enumerate(nodes_with_2_edges):
            if node in removed_nodes or node.node_type == 'station' or node.node_type == 'trajectory':
                continue

            # Find the two nodes, which are connected to the node by an edge.
            edge_1 = edges_connected_to_nodes_with_2_edges[index_1][0]
            if edge_1.node1 == node:
                connected_node_1 = edge_1.node2
            elif edge_1.node2 == node:
                connected_node_1 = edge_1.node1
            edge_2 = edges_connected_to_nodes_with_2_edges[index_1][1]
            if edge_2.node1 == node:
                connected_node_2 = edge_2.node2
            elif edge_2.node2 == node:
                connected_node_2 = edge_2.node1

            # Check if the two nodes can be connected by an edge.
            line = shapely.LineString([connected_node_1.position, connected_node_2.position])
            line_clearance, _ = self.check_line_clearance_without(connected_node_1, connected_node_2, line, node, edge_1, edge_2)
            if line_clearance:
                # Remove the node.
                self.graph.remove_node(node)
                removed_nodes.append(node)

                # Add edge between the two nodes.
                self.graph.add_edge(connected_node_1, connected_node_2, line, boundary_edge=True)

                # Remove nodes following the edges along the direction of connected_node_1.
                while connected_node_1 in nodes_with_2_edges:
                    # Find the node which is connected to connected_node_1, which is not connected_node_2. Update connected_node_1.
                    node = connected_node_1
                    connected_edges = edges_connected_to_nodes_with_2_edges[nodes_with_2_edges.index(connected_node_1)]
                    if connected_edges[0].node1 == connected_node_1:
                        connected_node_1 = connected_edges[0].node2
                    elif connected_edges[0].node2 == connected_node_1:
                        connected_node_1 = connected_edges[0].node1
                    elif connected_edges[1].node1 == connected_node_1:
                        connected_node_1 = connected_edges[1].node2
                    elif connected_edges[1].node2 == connected_node_1:
                        connected_node_1 = connected_edges[1].node1

                    # Check if the two nodes can be connected by an edge.
                    line = shapely.LineString([connected_node_1.position, connected_node_2.position])
                    line_clearance, _ = self.check_line_clearance_without(connected_node_1, connected_node_2, line, node,
                                                                          connected_edges[0], connected_edges[1])
                    if line_clearance:
                        # Remove the node.
                        self.graph.remove_node(node)
                        removed_nodes.append(node)

                        # Add edge between the two nodes.
                        self.graph.add_edge(connected_node_1, connected_node_2, line, boundary_edge=True)

                    else:
                        # Update connected_node_1.
                        connected_node_1 = node
                        break

                # Remove nodes following the edges along the direction of connected_node_2.
                while connected_node_2 in nodes_with_2_edges:
                    # Find the node which is connected to connected_node_2, which is not connected_node_1. Update connected_node_2.
                    node = connected_node_2
                    connected_edges = edges_connected_to_nodes_with_2_edges[nodes_with_2_edges.index(connected_node_2)]
                    if connected_edges[0].node1 == connected_node_2:
                        connected_node_2 = connected_edges[0].node2
                    elif connected_edges[0].node2 == connected_node_2:
                        connected_node_2 = connected_edges[0].node1
                    elif connected_edges[1].node1 == connected_node_2:
                        connected_node_2 = connected_edges[1].node2
                    elif connected_edges[1].node2 == connected_node_2:
                        connected_node_2 = connected_edges[1].node1

                    # Check if the two nodes can be connected by an edge.
                    line = shapely.LineString([connected_node_1.position, connected_node_2.position])
                    line_clearance, _ = self.check_line_clearance_without(connected_node_1, connected_node_2, line, node,
                                                                          connected_edges[0], connected_edges[1])
                    if line_clearance:
                        # Remove the node.
                        self.graph.remove_node(node)
                        removed_nodes.append(node)

                        # Add edge between the two nodes.
                        self.graph.add_edge(connected_node_1, connected_node_2, line, boundary_edge=True)

                    else:
                        # Update connected_node_2.
                        connected_node_2 = node
                        break

    def remove_nodes_and_edges_out_of_table_configuration(self) -> None:
        """
        Removes nodes and edges that are not within the table configuration.

        Args:
            None
        """
        node_count = len(self.graph.nodes)
        removed_nodes = 0
        for node_index in range(node_count):
            if not self.graph.nodes[node_index - removed_nodes].shapely_point.within(
                    self.table_config.table_configuration_polygon_cfree_round):
                if self.graph.nodes[node_index - removed_nodes].position in self.station_config.station_trajectory_nodes:
                    pass  # raise ValueError("Station trajectory nodes cannot be removed.")
                elif self.graph.nodes[node_index - removed_nodes].position in self.station_config.station_nodes:
                    # Station nodes can be outside the table configuration. They are not removed.
                    pass  # continue

                # Remove nodes if they are out of the table configuration.
                self.graph.remove_node(self.graph.nodes[node_index - removed_nodes])
                removed_nodes += 1

        edge_count = len(self.graph.edges)
        removed_edges = 0
        for edge_index in range(edge_count):
            if not self.graph.edges[edge_index - removed_edges].shapely_line.within(
                    self.table_config.table_configuration_polygon_cfree_round):
                if self.graph.edges[edge_index - removed_edges].edge_type == 'station <-> trajectory':
                    # Edges between station and station trajectory nodes can be outside the table configuration. They are not removed.
                    pass  # continue
                # Remove edges if they are out of the table configuration.
                # Here only edges are removed, which were not connected to removed nodes. These edges were already removed.
                self.graph.remove_edge(self.graph.edges[edge_index - removed_edges])
                removed_edges += 1

    def remove_nodes_and_edges_in_station_area(self, station) -> None:
        """
        Removes nodes and edges that are within the station area.

        Args:
            station (object): Station object.
        """
        # Define station area considering the station trajectory nodes (and station buffer nodes).
        station_area_polygon = shapely.Polygon(station.station_corner_nodes)
        station_area_polygon = station_area_polygon.buffer(self.boundary_distance)
        for station_trajectory_node in station.station_trajectory_nodes:
            station_trajectory_polygon = shapely.Polygon([(station_trajectory_node[0] - 0.1, station_trajectory_node[1] - 0.1),
                                                          (station_trajectory_node[0] + 0.1, station_trajectory_node[1] - 0.1),
                                                          (station_trajectory_node[0] + 0.1, station_trajectory_node[1] + 0.1),
                                                          (station_trajectory_node[0] - 0.1, station_trajectory_node[1] + 0.1)])
            station_trajectory_polygon = station_trajectory_polygon.buffer(self.required_node_clearance)
            station_area_polygon = station_area_polygon.union(station_trajectory_polygon)
        for station_buffer_node in station.station_buffer_nodes:
            station_buffer_polygon = shapely.Polygon([(station_buffer_node[0] - 0.1, station_buffer_node[1] - 0.1),
                                                      (station_buffer_node[0] + 0.1, station_buffer_node[1] - 0.1),
                                                      (station_buffer_node[0] + 0.1, station_buffer_node[1] + 0.1),
                                                      (station_buffer_node[0] - 0.1, station_buffer_node[1] + 0.1)])
            station_buffer_polygon = station_buffer_polygon.buffer(self.required_node_clearance)
            station_area_polygon = station_area_polygon.union(station_buffer_polygon)

        # Remove nodes and edges within the station area or are intersecting with the station area.
        node_count = len(self.graph.nodes)
        removed_nodes = 0
        for node_index in range(node_count):
            if self.graph.nodes[node_index - removed_nodes].shapely_point.within(station_area_polygon):
                if self.graph.nodes[node_index - removed_nodes].position in self.station_config.station_trajectory_nodes:
                    # Station trajectory nodes of the new stations are not added yet. They are not considered.
                    pass # raise ValueError("Station trajectory nodes cannot be removed.")
                else:
                    # Remove nodes if they are within the station area.
                    self.graph.remove_node(self.graph.nodes[node_index - removed_nodes])
                    removed_nodes += 1

        edge_count = len(self.graph.edges)
        removed_edges = 0
        for edge_index in range(edge_count):
            if self.graph.edges[edge_index - removed_edges].shapely_line.within(station_area_polygon) \
                    or self.graph.edges[edge_index - removed_edges].shapely_line.intersects(station_area_polygon):
                if self.graph.edges[edge_index - removed_edges].edge_type == 'station <-> trajectory':
                    # Edges between station and station trajectory nodes of the new stations are not added yet. They are not considered.
                    raise ValueError("station <-> trajectory edges cannot be removed.")
                # Remove edges if they are within the station area.
                # Here only edges are removed, which were not connected to removed nodes. These edges were already removed.
                self.graph.remove_edge(self.graph.edges[edge_index - removed_edges])
                removed_edges += 1

    # ------------------------ Edges ------------------------
    def connect_k_nearest_nodes(self, nodes, number_connections, without_distance_check=False, force_directed_graph=False) -> None:
        """
        Function connects the k nearest nodes and defines edges.
        """
        # Each iteration is very time consuming due to the sorting. It gets worse the more nodes exist.

        for i in range(1):
            if i == 0:
                max_index = 8
                max_distance = 70
                number_connections = 2  # 4
            elif i == 1:
                max_index = 20
                max_distance = 70
                number_connections = 2
            elif i == 2:
                max_index = 100
                max_distance = 200
                number_connections = 1
            elif i == 3:
                max_index = 300
                max_distance = 500
                number_connections = 2

            # TODO: Order of nodes is random -> could an specific order be beneficial?
            for node_1 in nodes:
                close_nodes = []
                for node_2 in self.graph.nodes:
                    distance = math.dist(node_1.position, node_2.position)
                    if distance > 0 and distance <= max_distance:
                        close_nodes.append([node_2, distance])
                close_nodes_sorted = sorted(close_nodes, key=lambda p: p[1])
                edges_added = 0
                # Check nodes ordered by closeness to node_1.position.
                for index, closest_node in enumerate(close_nodes_sorted):
                    # TODO: Find a way to generate good networks robustly.
                    if closest_node[1] == 0 or index >= max_index or closest_node[1] >= max_distance:
                        continue
                    line = shapely.LineString([node_1.position, closest_node[0].position])
                    line_clearance, _ = self.check_line_clearance(node_1.position, closest_node[0].position, line,
                                                                  without_distance_check=True, force_directed_graph=True)
                    if line_clearance:
                        self.graph.add_edge(node_1, closest_node[0], line)
                        edges_added += 1
                        if edges_added == number_connections:
                            break

            # for node_1 in nodes:
            #     close_nodes = []
            #     for node_2 in self.graph.nodes:
            #         distance = math.dist(node_1.position, node_2.position)
            #         if distance > 0:
            #             close_nodes.append([node_2, distance])
            #     close_nodes_sorted = sorted(close_nodes, key=lambda p: p[1])
            #     edges_added = 0
            #     # Check nodes ordered by closeness to node_1.position.
            #     for index, closest_node in enumerate(close_nodes_sorted):
            #         # TODO: Find a way to generate good networks robustly.
            #         if closest_node[1] == 0 or index >= max_index or closest_node[1] >= max_distance:
            #             continue
            #         line = shapely.LineString([node_1.position, closest_node[0].position])
            #         line_clearance, _ = self.check_line_clearance(node_1.position, closest_node[0].position, line)
            #         if line_clearance:
            #             self.graph.add_edge(node_1, closest_node[0], line)
            #             edges_added += 1
            #             if edges_added == number_connections:
            #                 break

    def delaunay_triangulation(self, nodes, without_distance_check=False) -> None:
        """
        Function uses Delaunay triangulation to connect nodes and define edges.

        Args:
            nodes (list): List of nodes to be connected.
        """
        # Extract the positions of the nodes.
        positions = np.array([node.position for node in nodes])

        # Perform Delaunay triangulation on the positions.
        tri = Delaunay(positions)

        # Iterate over the triangles generated by the Delaunay triangulation.
        for triangle in tri.simplices:
            node1, node2, node3 = nodes[triangle[0]], nodes[triangle[1]], nodes[triangle[2]]

            # For each pair of nodes, create a line (edge) and check if it has the required clearance.
            # If it does, add the edge to the graph.

            # Line 1.
            line = shapely.LineString([node1.position, node2.position])
            if without_distance_check:
                line_clearance, _ = self.check_line_clearance(node1.position, node2.position, line, without_distance_check=True)
            else:
                line_clearance, _ = self.check_line_clearance(node1.position, node2.position, line)
            if line_clearance:
                self.graph.add_edge(node1, node2, line)

            # Line 2.
            line = shapely.LineString([node2.position, node3.position])
            if without_distance_check:
                line_clearance, _ = self.check_line_clearance(node2.position, node3.position, line, without_distance_check=True)
            else:
                line_clearance, _ = self.check_line_clearance(node2.position, node3.position, line)
            if line_clearance:
                self.graph.add_edge(node2, node3, line)

            # Line 3.
            line = shapely.LineString([node3.position, node1.position])
            if without_distance_check:
                line_clearance, _ = self.check_line_clearance(node3.position, node1.position, line, without_distance_check=True)
            else:
                line_clearance, _ = self.check_line_clearance(node3.position, node1.position, line)
            if line_clearance:
                self.graph.add_edge(node3, node1, line)

    def connect_station_to_station_trajectory_nodes(self) -> None:
        """
        Function connects the station trajectory nodes to the station nodes.
        """
        # Clearance to other nodes and edges is not checked.
        for station in self.station_config.stations:
            # Add station node.
            point = shapely.Point(station.station_node)
            if point not in self.graph.node_points:
                self.graph.add_node(station.station_node, point, 'station', orientation=station.station_orientation)
                station_node_object = self.graph.nodes[-1]
            else:
                station_node_object = self.graph.nodes[self.graph.node_points.index(point)]

            for index, station_trajectory_node in enumerate(station.station_trajectory_nodes):
                # Find corresponding graph node of station trajectory node.
                station_trajectory_graph_node = next(node for node in self.graph.nodes if node.position == station_trajectory_node)
                # Add edge between station node and station trajectory node.
                if len(station.station_trajectory_nodes) == 1:
                    line = shapely.LineString([station.station_node, station_trajectory_node])
                    line_clearance, _ = self.check_line_clearance(station_node_object, station_trajectory_graph_node, line,
                                                                  station_trajectory=True)
                    if line_clearance:
                        self.graph.add_edge(station_node_object, station_trajectory_graph_node, line,
                                            edge_type='station <-> trajectory', boundary_edge=False)
                elif len(station.station_trajectory_nodes) > 1:
                    if index == 0:
                        edge_direction = '2 -> 1'
                    elif index == 1:
                        edge_direction = '1 -> 2'
                    else:
                        raise ValueError("More than 2 station trajectory nodes.")
                    line = shapely.LineString([station.station_node, station_trajectory_node])
                    line_clearance, _ = self.check_line_clearance(station_node_object, station_trajectory_graph_node, line,
                                                                  station_trajectory=True)
                    if line_clearance:
                        self.graph.add_edge(station_node_object, station_trajectory_graph_node, line,
                                            edge_type='station <-> trajectory', boundary_edge=False,
                                            direction=edge_direction)

    def connect_station_trajectory_to_station_buffer_nodes(self) -> None:
        """
        Function connects the station buffer nodes to the station trajectory nodes.
        """
        for station in self.station_config.stations:
            for station_trajectory_node in station.station_trajectory_nodes:
                if station_trajectory_node not in self.graph.node_positions:
                    continue
                # Find corresponding graph node of station trajectory node.
                station_trajectory_graph_node = next(node for node in self.graph.nodes if node.position == station_trajectory_node)
                for station_buffer_node in station.station_buffer_nodes:
                    if station_buffer_node not in self.graph.node_positions \
                            or math.dist(station_buffer_node, station_trajectory_node) > self.buffer_node_distance + 1:
                        continue
                    # Find corresponding graph node of station buffer node.
                    station_buffer_graph_node = next(node for node in self.graph.nodes if node.position == station_buffer_node)
                    # Add edge between station trajectory node and station buffer node.
                    line = shapely.LineString([station_trajectory_node, station_buffer_node])
                    line_clearance, _ = self.check_line_clearance(station_trajectory_node, station_buffer_node, line)
                    if line_clearance:
                        self.graph.add_edge(station_trajectory_graph_node, station_buffer_graph_node, line,
                                            edge_type='trajectory <-> buffer', boundary_edge=True)

    def try_to_move_node_slightly(self, node_to_add, add_edges=False) -> tuple:
        """
        Try to move node slightly and check if node clearance is given.
        """
        node_positions = [(node_to_add[0] + 5, node_to_add[1]), (node_to_add[0] - 5, node_to_add[1]),
                          (node_to_add[0], node_to_add[1] + 5), (node_to_add[0], node_to_add[1] - 5),
                          (node_to_add[0] + 10, node_to_add[1]), (node_to_add[0] - 10, node_to_add[1]),
                          (node_to_add[0], node_to_add[1] + 10), (node_to_add[0], node_to_add[1] - 10)]
        for node_position in node_positions:
            node_position_point = shapely.Point(node_position)
            if add_edges:
                if min(node_position_point.distance(self.graph.node_points)) >= self.required_node_clearance \
                        and min(node_position_point.distance(self.graph.edges_lines)) >= self.required_node_edge_clearance:
                    return node_position, node_position_point

            elif min(node_position_point.distance(self.graph.node_points)) >= self.required_node_clearance:
                return node_position, node_position_point

        return None, None

    def try_to_connect_buffer_node(self, other_node, initial_buffer_node) -> object:
        """
        Move buffer node slightly and check if edge connection is possible.
        other_node: Node to which the buffer node should be connected.
        initial_buffer_node: Buffer node to be connected.
        """
        current_buffer_node_position = initial_buffer_node.position

        for station in self.station_config.stations:
            if current_buffer_node_position in station.station_buffer_nodes:
                min_distance = 1000000
                nearest_trajectory_node = None
                for station_trajectory_node in station.station_trajectory_nodes:
                    distance = math.dist(current_buffer_node_position, station_trajectory_node)
                    if distance < min_distance:
                        min_distance = distance
                        nearest_trajectory_node = station_trajectory_node
                break

        vector = (nearest_trajectory_node[0] - current_buffer_node_position[0],
                  nearest_trajectory_node[1] - current_buffer_node_position[1])

        buffer_node_positions = [(int(initial_buffer_node.position[0] - (vector[0] / min_distance) * 5),
                                  int(initial_buffer_node.position[1] - (vector[1] / min_distance) * 5)),
                                 (int(initial_buffer_node.position[0] - (vector[0] / min_distance) * 10),
                                  int(initial_buffer_node.position[1] - (vector[1] / min_distance) * 10)),
                                 (int(initial_buffer_node.position[0] - (vector[0] / min_distance) * 15),
                                  int(initial_buffer_node.position[1] - (vector[1] / min_distance) * 15)),
                                 (int(initial_buffer_node.position[0] - (vector[0] / min_distance) * 20),
                                  int(initial_buffer_node.position[1] - (vector[1] / min_distance) * 20))
                                 ]

        # buffer_node_positions = [(initial_buffer_node.position[0] + 5, initial_buffer_node.position[1]),
        #                          (initial_buffer_node.position[0] - 5, initial_buffer_node.position[1]),
        #                          (initial_buffer_node.position[0], initial_buffer_node.position[1] + 5),
        #                          (initial_buffer_node.position[0], initial_buffer_node.position[1] - 5),
        #                          (initial_buffer_node.position[0] + 10, initial_buffer_node.position[1]),
        #                          (initial_buffer_node.position[0] - 10, initial_buffer_node.position[1]),
        #                          (initial_buffer_node.position[0], initial_buffer_node.position[1] + 10),
        #                          (initial_buffer_node.position[0], initial_buffer_node.position[1] - 10),
        #                          (initial_buffer_node.position[0] + 15, initial_buffer_node.position[1]),
        #                          (initial_buffer_node.position[0] - 15, initial_buffer_node.position[1]),
        #                          (initial_buffer_node.position[0], initial_buffer_node.position[1] + 15),
        #                          (initial_buffer_node.position[0], initial_buffer_node.position[1] - 15),
        #                          (initial_buffer_node.position[0] + 20, initial_buffer_node.position[1]),
        #                          (initial_buffer_node.position[0] - 20, initial_buffer_node.position[1]),
        #                          (initial_buffer_node.position[0], initial_buffer_node.position[1] + 20),
        #                          (initial_buffer_node.position[0], initial_buffer_node.position[1] - 20)]

        for buffer_node_position in buffer_node_positions:
            node_update = self.graph.update_node_position(current_buffer_node_position, buffer_node_position,
                                                          check_clearance=True, node_edge_generator=self)
            if node_update:
                current_buffer_node_position = buffer_node_position
                line = shapely.LineString([other_node.position, buffer_node_position])
                line_clearance, _ = self.check_line_clearance(other_node.position, buffer_node_position, line)
                if line_clearance:
                    # Connect the nodes by edges.
                    self.graph.add_edge(other_node, initial_buffer_node, line, boundary_edge=True)
                    return initial_buffer_node

        return None

    def check_line_clearance(self, node_1, node_2, line, update_node_position=False,
                             station_trajectory=False, without_distance_check=False,
                             force_directed_graph=False) -> [bool, int]:
        """
        Check if line has clearance to nodes and edges.
        """
        line_clearance = False
        too_close_node_index = None

        if not without_distance_check:
            distance_line_points = line.distance(self.graph.node_points)
            # Check distance between new line and existing nodes.
            for index, distance_line_point in enumerate(distance_line_points):
                if 0 < distance_line_point < self.required_node_edge_clearance:
                    line_clearance_nodes = False
                    too_close_node_index = index
                    break
                else:
                    line_clearance_nodes = True
        else:
            # Distance between nodes and new line is not checked.
            line_clearance_nodes = True

        if line_clearance_nodes:
            if update_node_position:
                # When node position is updated. Not all checks are necessary.
                if line.within(self.table_config.table_configuration_polygon_cfree_round) \
                        and not any(line.crosses(self.graph.edges_lines)):
                    line_clearance = True
            elif station_trajectory:
                # For connection station nodes with station trajectory nodes. Not all checks are necessary.
                if not any(line.crosses(self.graph.edges_lines)) and not any(line.covers(self.graph.edges_lines)) \
                        and [node_1, node_2] not in self.graph.edges_nodes and [node_2, node_1] not in self.graph.edges_nodes:
                    line_clearance = True
            elif force_directed_graph:
                # Network for force-directed graph algorithm. Crossings are possible.
                # TODO: Only one crossing allowed.
                if line.within(self.table_config.table_configuration_polygon_cfree_round) \
                        and not any(line.covers(self.graph.edges_lines)) \
                        and [node_1, node_2] not in self.graph.edges_nodes and [node_2, node_1] not in self.graph.edges_nodes:
                    line_clearance = True
            else:
                # Normal case. All checks are necessary.
                if line.within(self.table_config.table_configuration_polygon_cfree_round) \
                        and not any(line.crosses(self.graph.edges_lines)) and not any(line.covers(self.graph.edges_lines)) \
                        and [node_1, node_2] not in self.graph.edges_nodes and [node_2, node_1] not in self.graph.edges_nodes:
                    line_clearance = True
        return line_clearance, too_close_node_index

    def check_line_clearance_without(self, node_1, node_2, line, node=None, node_edge_1=None, node_edge_2=None) -> [bool, int]:
        """
        Check if line has clearance to nodes and edges. Passed node and edges are not considered.
        """
        line_clearance = False
        too_close_node_index = None

        node_points = self.graph.node_points.copy()
        edges_lines = self.graph.edges_lines.copy()
        edges_nodes = self.graph.edges_nodes.copy()

        if node is not None:
            node_points.remove(node.shapely_point)

        if node_edge_1 is not None:
            edges_lines.remove(node_edge_1.shapely_line)

            if [node_edge_1.node1.position, node_edge_1.node2.position] in edges_nodes:
                edges_nodes.remove([node_edge_1.node1.position, node_edge_1.node2.position])
            elif [node_edge_1.node2.position, node_edge_1.node1.position] in edges_nodes:
                edges_nodes.remove([node_edge_1.node2.position, node_edge_1.node1.position])

        if node_edge_2 is not None:
            edges_lines.remove(node_edge_2.shapely_line)

            if [node_edge_2.node1.position, node_edge_2.node2.position] in edges_nodes:
                edges_nodes.remove([node_edge_2.node1.position, node_edge_2.node2.position])
            elif [node_edge_2.node2.position, node_edge_2.node1.position] in edges_nodes:
                edges_nodes.remove([node_edge_2.node2.position, node_edge_2.node1.position])

        distance_line_points = line.distance(node_points)
        # Check distance between new line and existing nodes.
        for index, distance_line_point in enumerate(distance_line_points):
            if 0 < distance_line_point < self.required_node_edge_clearance:
                line_clearance_nodes = False
                too_close_node_index = index
                break
            else:
                line_clearance_nodes = True

        if line_clearance_nodes:
            if line.within(self.table_config.table_configuration_polygon_cfree_round) \
                    and not any(line.crosses(edges_lines)) and not any(line.covers(edges_lines)) \
                    and [node_1, node_2] not in edges_nodes and [node_2, node_1] not in edges_nodes:
                line_clearance = True
        return line_clearance, too_close_node_index
