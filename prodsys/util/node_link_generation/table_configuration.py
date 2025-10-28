import numpy as np
import skimage
import math
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
from scipy.spatial import Voronoi, voronoi_plot_2d
import shapely
import pygeoops
from prodsys.util.node_link_generation.configuration import Configuration 


"""
BSD 3-Clause License

Copyright (c) 2023, pygeoops

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""


class Station:
    def __init__(self, station_number):
        self.station_number = station_number
        self.station_node = None
        self.station_orientation = None
        self.station_trajectory_nodes = []
        self.station_buffer_nodes = []
        self.station_corner_nodes = []


class StationConfiguration:
    def __init__(self, config, table_config):
        self.table_config = table_config
        self.buffer_node_distance = config.get(Configuration.Buffer_Node_Distance)
        self.stations = []
        self.station_nodes = []
        self.station_orientations = []
        self.station_trajectory_nodes = []
        self.station_buffer_nodes = []

    def add_stations(self, stations: list, visualization) -> None:
        """
        Function adds stations to the station configuration.
        """
        for station_nr, station in enumerate(stations["physical_objects"]):
            # TODO: Implement check, if station is positioned correctly.
            station_object = Station(station_nr)
            self.stations.append(station_object)

            self.station_nodes.append(tuple(station["pose"][:2]))
            self.station_orientations.append(station["pose"][2])
            station_object.station_node = tuple(station["pose"][:2])
            station_object.station_orientation = station["pose"][2]

            trajectory_nodes = self.get_trajectory_node_position(station)
            trajectory_nodes_cfree = self.check_station_nodes_cfree(trajectory_nodes)
            if len(trajectory_nodes_cfree) != len(trajectory_nodes):
                raise ValueError(str(len(trajectory_nodes) - len(trajectory_nodes_cfree)) + " trajectory nodes are not in cfree. \
                      Station number: " + str(station_nr) + " " + str(self.station_nodes[-1]))
            self.station_trajectory_nodes.extend([*trajectory_nodes_cfree])
            station_object.station_trajectory_nodes.extend([*trajectory_nodes_cfree])

            buffer_nodes = self.get_buffer_node_position(station, number_trajectory_nodes=len(trajectory_nodes_cfree),
                                                         buffer_distance=self.buffer_node_distance)
            buffer_nodes = self.check_station_nodes_cfree(buffer_nodes)
            self.station_buffer_nodes.extend([*buffer_nodes])
            station_object.station_buffer_nodes.extend([*buffer_nodes])

            if "stations_layer" not in visualization.occupancy_matrices.keys():
                visualization.add_free_layer("stations_layer")
            station_corners = self.get_station_corner_nodes(station)
            station_object.station_corner_nodes.extend(station_corners)
            visualization.draw_polygon_to_layer("stations_layer", station_corners)

    def remove_all_stations(self, node_edge_generator, visualization):
        """
        Function deletes all stations as well as the corresponding nodes and edges.
        """
        visualization.add_free_layer("stations_layer")
        self.stations = []
        self.station_nodes = []
        self.station_orientations = []
        self.station_trajectory_nodes = []
        self.station_buffer_nodes = []
        node_edge_generator.graph.remove_station_nodes_and_edges()

    # Check nodes and edges.
    def check_station_nodes_cfree(self, nodes: list) -> list:
        """
        Check if nodes are in cfree.
        """
        nodes_in_cfree = []
        for node in nodes:
            point = shapely.Point(node)
            if point.within(self.table_config.table_configuration_polygon_cfree):
                nodes_in_cfree.append(node)
        return nodes_in_cfree

    def get_trajectory_node_position(self, station: tuple) -> list:
        """
        Function returns the trajectory nodes of a station. Stations are quadratic.
        """
        # Define local trajectory nodes relative to the station center node.
        trajectory_in_node = (station["poi"]["in_port.trajectory_node"][0], station["poi"]["in_port.trajectory_node"][1])
        trajectory_out_node = (station["poi"]["out_port.trajectory_node"][0], station["poi"]["out_port.trajectory_node"][1])
        if trajectory_in_node == trajectory_out_node:
            local_trajectory_nodes = [trajectory_in_node]
        elif trajectory_in_node != trajectory_out_node:
            local_trajectory_nodes = [trajectory_in_node, trajectory_out_node]

        trajectory_nodes = self.rotate_stations(station, local_trajectory_nodes)

        return trajectory_nodes

    def get_buffer_node_position(self, station: tuple, number_trajectory_nodes: int, buffer_distance: int) -> list:
        """
        Function returns the buffer nodes of a station. Stations are quadratic.
        """
        # Define local buffer nodes relative to the station center node.
        if number_trajectory_nodes == 1:
            local_buffer_nodes = [(station["poi"]["in_port.trajectory_node"][0], - buffer_distance),
                                  (station["poi"]["in_port.trajectory_node"][0], buffer_distance)]
            #                      (station["poi"]["in_port.trajectory_node"][0] + buffer_distance, 0),
            #                      (station["poi"]["in_port.trajectory_node"][0] + buffer_distance, - buffer_distance),
            #                      (station["poi"]["in_port.trajectory_node"][0] + buffer_distance, buffer_distance)]

        elif number_trajectory_nodes == 2:
            local_buffer_nodes = [(station["poi"]["in_port.trajectory_node"][0], - buffer_distance),
                                  (station["poi"]["in_port.trajectory_node"][0], buffer_distance),
                                  (station["poi"]["out_port.trajectory_node"][0], - buffer_distance),
                                  (station["poi"]["out_port.trajectory_node"][0], buffer_distance)]

        buffer_nodes = self.rotate_stations(station, local_buffer_nodes)

        return buffer_nodes

    def get_station_corner_nodes(self, station: tuple) -> list:
        """
        Function returns the corner nodes of a station. Stations are quadratic.
        """
        # Define the corners of the station in its local coordinate system.
        local_corners = [(station["bounding_box"][0][0], station["bounding_box"][0][1]),
                         (station["bounding_box"][1][0], station["bounding_box"][0][1]),
                         (station["bounding_box"][1][0], station["bounding_box"][1][1]),
                         (station["bounding_box"][0][0], station["bounding_box"][1][1])]

        station_corners = self.rotate_stations(station, local_corners)

        return station_corners

    def rotate_stations(self, station, local_nodes) -> list:
        """
        Function calculates the global coordinates of local station nodes of rotated stations.
        """
        # Convert the orientation to radians.
        theta = math.radians(station["pose"][2])

        # Define the rotation matrix.
        rotation_matrix = [[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]]

        # Rotate the corners and translate them to the global coordinate system.
        station_corners = [(round(station["pose"][0] + rotation_matrix[0][0] * node[0] + rotation_matrix[0][1] * node[1]),
                            round(station["pose"][1] + rotation_matrix[1][0] * node[0] + rotation_matrix[1][1] * node[1]))
                           for node in local_nodes]

        return station_corners


class Table:
    def __init__(self, table_number=None):
        self.table_number = table_number
        self.table_orientation = None
        self.table_corner_nodes = []
        self.table_configuration_intersection_middle_offset_nodes = []
        self.table_polygon = None


class TableConfiguration:
    def __init__(self, config):
        # Boundary conditions.
        self.boundary_distance = config.get(Configuration.Boundary_Distance)
        self.required_node_clearance = config.get(Configuration.Min_Node_Distance)
        self.required_node_edge_clearance = config.get(Configuration.Min_Node_Edge_Distance)

        # Table configuration.
        self.tables = []
        self.table_configuration_intersection_middle_nodes = []
        self.table_configuration_corner_nodes = []
        self.table_configuration_corner_nodes_cfree = []
        self.table_configuration_polygon = []
        self.table_configuration_polygon_cfree = []
        self.table_configuration_polygon_cfree_round = []
        self.table_configuration_polygon_without_stations = []

        # Medial axis.
        self.medial_axis = None
        self.medial_axis_nodes = []
        self.medial_axis_edges = []

        # Zones.
        self.zones_polygons = []
        self.zones_directions = []
        self.zones_edges = []

    def reset_table_configuration(self, visualization, update=False):
        """
        Function is used to reset the table configuration.
        """
        # Table configuration.
        if update:
            # Reset table configuration polygon. Table configuration polygon is the union of all table modules without the stations.
            self.table_configuration_polygon = self.table_configuration_polygon_without_stations
        else:
            # Reset table configuration completely.
            visualization.add_table_layer()
            self.tables = []
            self.table_configuration_intersection_middle_nodes = []
            self.table_configuration_corner_nodes = []
            self.table_configuration_corner_nodes_cfree = []
            self.table_configuration_polygon = []
            self.table_configuration_polygon_cfree = []
            self.table_configuration_polygon_cfree_round = []
            self.table_configuration_polygon_without_stations = []

        # Medial axis.
        self.medial_axis = None
        self.medial_axis_nodes = []
        self.medial_axis_edges = []

        # Zones.
        self.zones_polygons = []
        self.zones_directions = []
        self.zones_edges = []

    def add_table(self, table_corners_poses, visualization, layer_id="table_layer") -> None: #MARKER
        """
        Function adds table modules. Table layer is adapted for visualization.
        table_corners_poses: List of poses (x, y, theta) of the corners of the table module.
                            x, y are the coordinates of the corner. theta is the orientation of the table module.
        visualization: Visualization object.
        layer_id: Layer id for visualization.
        """
        if "table_layer" not in visualization.occupancy_matrices.keys():
            # Add a table layer if no table layer exists yet.
            visualization.add_table_layer()

        # Initialize table object.
        table_object = Table()
        self.tables.append(table_object)

        # Extract the corner nodes of the table module.
        table_corner_nodes = []
        for corner in table_corners_poses:
            table_corner_nodes.append((corner['pose'][0], corner['pose'][1]))

        # Define table module as polygon.
        table_polygon = shapely.Polygon(table_corner_nodes)

        if self.table_configuration_polygon == []:
            # No table module added so far.
            self.table_configuration_polygon = table_polygon

        # Check if table module is overlapping with the existing table modules. #MARKER kann man das entfernen oder wird es sonst buggy?
        #elif not table_polygon.overlaps(self.table_configuration_polygon) and not table_polygon.within(self.table_configuration_polygon):
        #    # Define table polygon of table object for calculate_intersection_nodes.
        #    table_object.table_polygon = table_polygon
        #    # Check if the polygons intersect.
        #    if table_polygon.intersects(self.table_configuration_polygon):
        #        # Extract the intersection line(s) of the two polygons.
        #        intersection_line = table_polygon.intersection(self.table_configuration_polygon)
        #        self.calculate_intersection_nodes(intersection_line)
#
        #    # Define table configuration polygon.
        #    self.table_configuration_polygon = shapely.unary_union([table_polygon, self.table_configuration_polygon])
#
        #else:
        #    raise ValueError("Table module is overlapping with the existing table modules or is within the existing table configuration: " + str(table_corner_nodes))

        # Table module is not overlapping with the existing table modules and can be added.
        table_object.table_orientation = table_corners_poses[0]['pose'][2]
        table_object.table_polygon = table_polygon
        table_object.table_corner_nodes = table_corner_nodes

        # Add table module for visualization.
        # TODO: How to handle case when table is not parallel to the axes or table has more than 4 corners?
        visualization.occupancy_matrices[layer_id][int(table_corner_nodes[0][1]):int(table_corner_nodes[2][1]) + 1,
                                                    int(table_corner_nodes[0][0]):int(table_corner_nodes[2][0]) + 1] = 0

    def remove_table(self, table_corner_nodes, visualization, layer_id="table_layer") -> None:
        """
        Function removes table modules. Table layer is adapted for visualization.
        table_corner_nodes: Corner nodes of the table modules. List of (x, y) coordinates.
        visualization: Visualization object.
        layer_id: Layer id for visualization.
        """
        # TODO: Visualization is not correct after table modules are removed. Reset table configuration and add all tables again is easier.
        # Define table module as polygon.
        table_polygon = shapely.Polygon(table_corner_nodes)

        # Check if table module exists.
        remove_table = False
        for table in self.tables:
            if table.table_polygon == table_polygon:
                remove_table = True
                table_object = table

        if not remove_table:
            raise ValueError("Table module does not exist.")

        # Table module exists and can be removed.
        self.table_configuration_polygon = self.table_configuration_polygon.difference(table_polygon)
        self.tables.remove(table_object)

        # Remove table module for visualization.
        # TODO: How to handle case when table is not parallel to the axes or table has more than 4 corners?
        visualization.occupancy_matrices[layer_id][table_corner_nodes[0][1]:table_corner_nodes[2][1] + 1,
                                                   table_corner_nodes[0][0]:table_corner_nodes[2][0] + 1] = 1

    def generate_table_configuration(self) -> None:
        """
        Function extracts the corner nodes and the usable corner nodes for the vehicles of the table configuration.
        """
        if self.table_configuration_corner_nodes != [] and self.table_configuration_corner_nodes_cfree != []:
            # Reset table configuration corner nodes.
            self.table_configuration_corner_nodes = []
            self.table_configuration_corner_nodes_cfree = []

        # Remove intermediate nodes of the polygon along an edge.
        # Now interior and exterior nodes of the polygon are only corner nodes of the polygon.
        self.table_configuration_polygon = self.table_configuration_polygon.buffer(-1, join_style=2)
        self.table_configuration_polygon = self.table_configuration_polygon.buffer(+1, join_style=2)

        # Store a version of the table configuration polygon, which remains unchanged when stations are added.
        self.table_configuration_polygon_without_stations = self.table_configuration_polygon.buffer(-1, join_style=2)
        self.table_configuration_polygon_without_stations = self.table_configuration_polygon_without_stations.buffer(+1, join_style=2)

        # Define table configuration corner nodes. Nodes should lie within the table configuration polygon, not at the outer edge.
        self.table_configuration_corner_nodes = self.update_table_configuration_corner_nodes(
            self.table_configuration_polygon.buffer(- 0.01, join_style=2))

        # Define usable space for vehicles.
        self.table_configuration_polygon_cfree = self.table_configuration_polygon.buffer(0.01 - self.boundary_distance, join_style=2)
        self.table_configuration_polygon_cfree_round = self.table_configuration_polygon.buffer(0.01 - self.boundary_distance)

        # Define usable corner nodes of the table configuration for the vehicles.
        # Nodes should lie within the table configuration cfree polygon, not at the outer edge.
        self.table_configuration_corner_nodes_cfree = self.update_table_configuration_corner_nodes(
            self.table_configuration_polygon.buffer(- self.boundary_distance, join_style=2))

    def table_configuration_with_stations(self, station_config):
        """
        Function extracts the corner nodes and the usable corner nodes for the vehicles
        of the table configuration considering the position of the stations.
        """
        # For all stations, check if they are positioned (partly) on the table configuration.
        for station in station_config.stations:
            station_area = shapely.Polygon(station.station_corner_nodes)
            if station_area.intersects(self.table_configuration_polygon):
                # Station is (partly) on the table configuration. Adjust the polygon of the table configuration.
                self.table_configuration_polygon = self.table_configuration_polygon.difference(station_area)

        # Define the usable space as well as the table configuration corner nodes and usable corner nodes for the vehicles.
        # Nodes should lie within the table configuration polygons, not at the outer edge.
        self.table_configuration_polygon_cfree = self.table_configuration_polygon.buffer(0.01 - self.boundary_distance, join_style=2)
        self.table_configuration_polygon_cfree_round = self.table_configuration_polygon.buffer(0.01 - self.boundary_distance)
        self.table_configuration_corner_nodes = self.update_table_configuration_corner_nodes(
            self.table_configuration_polygon.buffer(- 0.01, join_style=2))
        self.table_configuration_corner_nodes_cfree = self.update_table_configuration_corner_nodes(
            self.table_configuration_polygon.buffer(- self.boundary_distance, join_style=2))

    def update_table_configuration_corner_nodes(self, polygon) -> list:
        """
        Function orders the table configuration corner nodes of a given polygon.
        Lists of ordered corner nodes starts with the lower left corner node and continues counter-clockwise.
        - [0]: Ordered list of corner nodes of exterior.
        - [1]: Ordered list of corner nodes of first interior (if existing).
        - [2]: Ordered list of corner nodes of second interior (if existing).
        - [3]: ...
        return: List of ordered lists of table configuration corner nodes.
        """
        corner_nodes = []
        ordered_corner_nodes = []

        # Extract exterior corner nodes.
        x, y = polygon.exterior.xy
        for i in range(len(x)):
            if len(corner_nodes) == 0:
                corner_nodes.append([])
                corner_nodes[0].append((x[i], y[i]))
            else:
                corner_nodes[0].append((x[i], y[i]))

        # Extract interior corner nodes. Interior corner nodes only exist, if polygon has a hole/holes in the middle.
        for index in range(len(polygon.interiors)):
            x, y = polygon.interiors[index].xy
            for i in range(len(x)):
                # TODO: Remove intermediate nodes along an edge.
                if len(corner_nodes) == index + 1:
                    corner_nodes.append([])
                    corner_nodes[index + 1].append((x[i], y[i]))
                else:
                    corner_nodes[index + 1].append((x[i], y[i]))

        # Reorder corner nodes. Start at left lower corner and ordered counter-clockwise.
        ordered_corner_nodes = corner_nodes
        for loop_index, corner_nodes_loop in enumerate(corner_nodes):
            corner_nodes_loop.pop(-1)
            start_index = corner_nodes_loop.index(min(corner_nodes_loop))
            part1 = corner_nodes_loop[start_index:]
            part2 = corner_nodes_loop[:start_index]
            ordered_corner_nodes[loop_index] = part1 + part2
            if ordered_corner_nodes[loop_index][0][0] == ordered_corner_nodes[loop_index][1][0]:
                # Corner nodes 1 and 2 have the same x value. Corner nodes are ordered clockwise.
                # Direction must be changed to counter-clockwise.
                ordered_corner_nodes[loop_index].append(ordered_corner_nodes[loop_index][0])
                ordered_corner_nodes[loop_index].reverse()
                ordered_corner_nodes[loop_index].pop(-1)
        return ordered_corner_nodes

    def check_corner_type(self, corner_node) -> str:
        """
        Function checks the type of a corner node of the table configuration.
        return: Type of the corner node. 'convex' or 'concave'.
        """
        for i in [0, 1]:
            if i == 0:
                # Check diagonal neighbor nodes of the corner node.
                neighbor_nodes = [(corner_node[0] - 1, corner_node[1] - 1), (corner_node[0] + 1, corner_node[1] - 1),
                                  (corner_node[0] + 1, corner_node[1] + 1), (corner_node[0] - 1, corner_node[1] + 1)]
            elif i == 1:
                # Check vertical and horizontal neighbor nodes of the corner node.
                neighbor_nodes = [(corner_node[0] - 1, corner_node[1]), (corner_node[0] + 1, corner_node[1]),
                                  (corner_node[0], corner_node[1] - 1), (corner_node[0], corner_node[1] + 1)]
            neighbor_points = [shapely.Point(neighbor_node) for neighbor_node in neighbor_nodes]

            neighbor_points_in_cfree = 0
            for neighbor_point in neighbor_points:
                if neighbor_point.within(self.table_configuration_polygon_cfree):
                    neighbor_points_in_cfree += 1

            if neighbor_points_in_cfree == 3:
                corner_type = 'convex'
                return corner_type
            elif neighbor_points_in_cfree == 1:
                corner_type = 'concave'
                return corner_type
            else:
                corner_type = 'undefined'

        return corner_type

    def define_table_nodes(self, table) -> list:
        """
        Function defines nodes on predefined positions on the table module.
        On each table module, 3 nodes are defined. One node is positioned in the middle of the table module.
        The other two nodes are positioned at the left and right side of the table module.
        The distance between the middle node and the left and right node is 33 cm.
        Distance is defined for vehicles that have a rotation diameter of at most 33 cm.
        """
        table_nodes = []

        # Define table nodes based on the given table module.
        table_nodes.append((table.table_polygon.centroid.x, table.table_polygon.centroid.y))
        if table.table_orientation == 0:
            table_nodes.append((table.table_polygon.centroid.x - 33, table.table_polygon.centroid.y))
            table_nodes.append((table.table_polygon.centroid.x + 33, table.table_polygon.centroid.y))
        elif table.table_orientation == 90:
            table_nodes.append((table.table_polygon.centroid.x, table.table_polygon.centroid.y - 33))
            table_nodes.append((table.table_polygon.centroid.x, table.table_polygon.centroid.y + 33))

        return table_nodes

    def calculate_intersection_nodes(self, intersection_line, parallel_offset=10) -> None:
        """
        Function calculates the intersection nodes of table modules based on the intersection line.
        """
        # Check if the intersection line is a line or a multi line.
        if isinstance(intersection_line, shapely.LineString):
            # Calculate the middle point of the line.
            mid_point = intersection_line.interpolate(0.5, normalized=True)
            self.table_configuration_intersection_middle_nodes.append((mid_point.x, mid_point.y))

            # Define nodes at +parallel_offset and -parallel_offset distance from the middle point vertically to the intersection line.
            offset_line_positive = intersection_line.parallel_offset(parallel_offset, 'left')
            offset_line_negative = intersection_line.parallel_offset(parallel_offset, 'right')

            mid_point_positive = offset_line_positive.interpolate(0.5, normalized=True)
            mid_point_negative = offset_line_negative.interpolate(0.5, normalized=True)
            mid_point_positive_shapely = shapely.Point(mid_point_positive.x, mid_point_positive.y)
            mid_point_negative_shapely = shapely.Point(mid_point_negative.x, mid_point_negative.y)

            # Check to which table the nodes belong.
            for table in self.tables:
                if mid_point_positive_shapely.within(table.table_polygon):
                    table.table_configuration_intersection_middle_offset_nodes.append((mid_point_positive.x, mid_point_positive.y))
                if mid_point_negative_shapely.within(table.table_polygon):
                    table.table_configuration_intersection_middle_offset_nodes.append((mid_point_negative.x, mid_point_negative.y))

        elif isinstance(intersection_line, shapely.MultiLineString):
            # Calculate the middle point of the lines.
            for line in intersection_line.geoms:
                mid_point = line.interpolate(0.5, normalized=True)
                self.table_configuration_intersection_middle_nodes.append((mid_point.x, mid_point.y))

                # Define nodes at +parallel_offset and -parallel_offset distance from the middle point vertically to the intersection line.
                offset_line_positive = line.parallel_offset(parallel_offset, 'left')
                offset_line_negative = line.parallel_offset(parallel_offset, 'right')

                mid_point_positive = offset_line_positive.interpolate(0.5, normalized=True)
                mid_point_negative = offset_line_negative.interpolate(0.5, normalized=True)
                mid_point_positive_shapely = shapely.Point(mid_point_positive.x, mid_point_positive.y)
                mid_point_negative_shapely = shapely.Point(mid_point_negative.x, mid_point_negative.y)

                # Check to which table the nodes belong.
                for table in self.tables:
                    if mid_point_positive_shapely.within(table.table_polygon):
                        table.table_configuration_intersection_middle_offset_nodes.append((mid_point_positive.x, mid_point_positive.y))
                    if mid_point_negative_shapely.within(table.table_polygon):
                        table.table_configuration_intersection_middle_offset_nodes.append((mid_point_negative.x, mid_point_negative.y))

    def define_medial_axis(self) -> None:
        """
        Function defines the medial axis of the table configuration considering the stations.
        """
        # Define medial axis of the table configuration.
        self.medial_axis = pygeoops.centerline(self.table_configuration_polygon_cfree,
                                               densify_distance=-0.01, min_branch_length=0, simplifytolerance=-0.05)

        # Extract medial axis nodes and edges. Iterate over each LineString in the MultiLineString.
        for line in self.medial_axis.geoms:
            # Extract nodes from the LineString.
            line_nodes = list(line.coords)

            # Check distance to the table configuration corner nodes.
            corner_branch = False
            for line_node in line_nodes:
                # Calculate the distance to each corner node and find the minimum distance.
                for corner_nodes in self.table_configuration_corner_nodes_cfree:
                    distances = [math.dist(line_node, corner_node) for corner_node in corner_nodes]
                    min_distance = min(distances)

                    if min_distance < 4:
                        # LineString is too close to a corner node.
                        corner_branch = True
                        break

            if corner_branch:
                # Nodes and edges are not added, if it is a corner branch.
                continue

            # Add nodes to the medial axis nodes.
            self.medial_axis_nodes.extend(line_nodes)

            # Extract edges from the LineString and add them to the medial axis edges.
            line_edges = [(line_nodes[i], line_nodes[i+1]) for i in range(len(line_nodes) - 1)]
            self.medial_axis_edges.extend(line_edges)

        # Remove duplicate nodes.
        self.medial_axis_nodes = list(dict.fromkeys(self.medial_axis_nodes))

        # Define simplified medial axis without the corner branches.
        self.medial_axis = shapely.geometry.MultiLineString(self.medial_axis_edges)

    def define_zones(self, layout_nr=None) -> None:
        """
        Function defines zones of the table configuration.
        """
        corner_nodes_points = []
        corner_nodes_cfree = []
        corner_nodes_cfree_points = []

        # Add edges between the corner nodes of the table configuration (boundary of the table configuration).
        for nodes in self.table_configuration_corner_nodes:
            corner_nodes_points.extend([shapely.Point(node) for node in nodes])
            for node_index, corner_node in enumerate(nodes):
                if node_index == len(nodes) - 1:
                    self.zones_edges.append(shapely.LineString([corner_node, nodes[0]]))
                else:
                    self.zones_edges.append(shapely.LineString([corner_node, nodes[node_index + 1]]))

        # Define corner nodes in cfree.
        for nodes in self.table_configuration_corner_nodes_cfree:
            corner_nodes_cfree.extend(nodes)
            corner_nodes_cfree_points.extend([shapely.Point(node) for node in nodes])

        # Add edges between the corner nodes in cfree of the table configuration and the closest medial axis nodes.
        # In addition add edges between the corner nodes in cfree and the closest corner nodes of the table configuration.
        for corner_node_cfree in corner_nodes_cfree:
            # Calculate the distance to each medial axis node and find the minimum distance.
            distances = [math.dist(corner_node_cfree, medial_axis_node) for medial_axis_node in self.medial_axis_nodes]
            min_distance = min(distances)

            # Find the medial axis node with the minimum distance.
            min_distance_index = distances.index(min_distance)
            min_distance_node = self.medial_axis_nodes[min_distance_index]

            # Calculate the distance to each corner node and find the minimum distance. Exclude distance == 0.
            line = shapely.LineString([corner_node_cfree, min_distance_node])
            node_distances = line.distance(corner_nodes_cfree_points)
            min_node_distance = min([distance for distance in node_distances if distance != 0])

            # Add edge, if distance to corner nodes is large enough.
            if min_node_distance > 10:
                self.zones_edges.append(shapely.LineString([corner_node_cfree, min_distance_node]))

                # Find closest corner node and add edge.
                closest_corner_node = min(corner_nodes_points, key=lambda node: node.distance(shapely.Point(corner_node_cfree)))
                self.zones_edges.append(shapely.LineString([closest_corner_node, corner_node_cfree]))

        # Add medial axis edges.
        for line in self.medial_axis.geoms:
            self.zones_edges.append(line)

        # Create a MultiLineString object.
        self.zones_edges = shapely.geometry.MultiLineString(self.zones_edges)

        # Define polygons based on the zones edges.
        polygons = shapely.ops.polygonize(self.zones_edges)
        self.zones_polygons = list(polygons)

        # Remove polygons that are not within the table configuration.
        for polygon in self.zones_polygons:
            if not polygon.within(self.table_configuration_polygon):
                self.zones_polygons.remove(polygon)

        self.define_zones_directions(layout_nr)

    def define_zones_directions(self, layout_nr) -> None:
        """
        Function is used to define prioritized movement directions for the zones.
        Directions are right, left, up and down.
        """
        # TODO: Implement algorithm. Zones are currently hard coded for few layouts.
        for zone in self.zones_polygons:
            pass

        if layout_nr == 12:
            # Zones are defined counter-clockwise following the outer boundary of the table configuration. No inner boundary.
            self.zones_directions = ['right', 'up', 'left', 'up', 'left', 'down', 'left', 'down']
        elif layout_nr == 15:
            # Zones are defined clockwise following the outer boundary of the table configuration.
            # At the inner boundary, zones are defined counter-clockwise.
            self.zones_directions = ['left', 'down', 'right', 'up', 'right', 'up', 'left', 'down']
        else:
            self.zones_directions = []


class Visualization:
    def __init__(self, config, table_config, station_config, node_edge_generator):
        # Objects
        self.config = config
        self.table_config = table_config
        self.station_config = station_config
        self.node_edge_generator = node_edge_generator

        # Occupancy matrices.
        self.occupancy_matrices = {}

    def add_free_layer(self, layer_id: str) -> None:
        """
        Function adds a free layer (value 0 -> usable space) of the given layer_id. Layer is only used for visualization.
        """
        self.occupancy_matrices[layer_id] = np.zeros((self.config.get(Configuration.Dim_Y), self.config.get(Configuration.Dim_X)))

    def add_table_layer(self, layer_id="table_layer") -> None:
        """
        Function adds a table layer (value 1 -> non-usable space). Table modules are added separately (value 0 -> usable space).
        Layer is only used for visualization.
        """
        self.occupancy_matrices[layer_id] = np.ones((self.config.get(Configuration.Dim_Y), self.config.get(Configuration.Dim_X))) \
            * self.config.get(Configuration.Blocked_Space_Value)
        self.occupancy_matrices[layer_id][0, 0] = 1

    def add_dilation_difference_layer(self, value: float = 0.6, kernel_radius: int = 0, layer_id: str = 'dilation_difference_layer') -> None:
        """
        Function adds a dilation difference layer (expanded non-usable space). Layer is only used for visualization.
        """
        self.occupancy_matrices[layer_id] = np.zeros((self.config.get(Configuration.Dim_Y), self.config.get(Configuration.Dim_X)))

        dilated_layers = self.get_dialated_occupancy_layers(None, self.config.get(Configuration.Boundary_Distance))
        occupancy_layers = self.get_merged_occupancy_layers(None)

        self.occupancy_matrices[layer_id] = (dilated_layers - occupancy_layers) * self.config.get(Configuration.Blocked_Space_Value) * value

    def calculate_padding(self, current_shape, new_shape):
        """
        Function calculates the padding needed for the current layer to match the size of the new layer.
        """
        padding_y = (0, new_shape[0] - current_shape[0]) if new_shape[0] > current_shape[0] else (0, 0)
        padding_x = (0, new_shape[1] - current_shape[1]) if new_shape[1] > current_shape[1] else (0, 0)

        return padding_y, padding_x

    def adjust_layer_dimensions(self) -> None:
        """
        Function adjusts the dimensions of the layers to the dimensions of the production layout.
        """
        # Remove dilation difference layer.
        if 'dilation_difference_layer' in self.occupancy_matrices.keys():
            self.occupancy_matrices.pop('dilation_difference_layer')

        # Adjust the dimensions of the layers to the dimensions of the production layout.
        for layer_id, current_layer in self.occupancy_matrices.items():
            if layer_id == "table_layer":
                new_layer = np.ones((self.config.get(Configuration.Dim_Y), self.config.get(Configuration.Dim_X)))
                fill_value = self.config.get(Configuration.Blocked_Space_Value)
            elif layer_id == "stations_layer":
                new_layer = np.zeros((self.config.get(Configuration.Dim_Y), self.config.get(Configuration.Dim_X)))
                fill_value = 0
            else:
                continue

            # Calculate the padding needed for the current layer
            padding_y, padding_x = self.calculate_padding(current_layer.shape, new_layer.shape)

            # If current_layer is smaller in y direction, pad it to match the size of new_layer
            if current_layer.shape[0] < new_layer.shape[0]:
                current_layer = np.pad(current_layer, (padding_y, (0, 0)), mode='constant', constant_values=fill_value)
            # If current_layer is larger in y direction, slice it to match the size of new_layer
            elif current_layer.shape[0] > new_layer.shape[0]:
                current_layer = current_layer[:new_layer.shape[0], :]

            # If current_layer is smaller in x direction, pad it to match the size of new_layer
            if current_layer.shape[1] < new_layer.shape[1]:
                current_layer = np.pad(current_layer, ((0, 0), padding_x), mode='constant', constant_values=fill_value)
            # If current_layer is larger in x direction, slice it to match the size of new_layer
            elif current_layer.shape[1] > new_layer.shape[1]:
                current_layer = current_layer[:, :new_layer.shape[1]]

            # Store the adjusted layer
            self.occupancy_matrices[layer_id] = current_layer

    def get_dialated_occupancy_layers(self, layer_ids: str = None, kernel_radius: int = 0) -> np.array:

        dialated_occupancy_layer = self.get_merged_occupancy_layers(layer_ids)

        if kernel_radius != 0:
            dialated_occupancy_layer = skimage.morphology.isotropic_dilation(dialated_occupancy_layer, kernel_radius, out=None, spacing=None)

        return dialated_occupancy_layer

    def get_merged_occupancy_layers(self, ids: list = None) -> np.array:

        merged_occupancy_layers = self.get_occupancy_layers(ids)
        stacked_occupancy_matrices = np.maximum.reduce(merged_occupancy_layers)

        return stacked_occupancy_matrices

    def get_occupancy_layer(self, layer_id: str) -> np.array:

        return self.occupancy_matrices[layer_id]

    def get_occupancy_layers(self, layer_ids: str = None) -> list:

        occupancy_matrices = []

        if layer_ids is None:
            layer_ids = list(self.occupancy_matrices.keys())

        for id in layer_ids:
            occupancy_matrices.append(self.get_occupancy_layer(id))

        return occupancy_matrices

    def get_occupied_coordinates(self, ids: list = None) -> np.array:
        # TODO: Function is not used.

        coordinates = np.nonzero(self.get_merged_occupancy_layers(ids))

        return coordinates

    def get_unoccupied_cooridnates_sampled(self, sampling_distance: int, dialation_radius: int = 0, ids: list = None) -> list:
        # TODO: Function is not used.

        sample_grid = self.get_dialated_occupancy_layers(ids, dialation_radius)
        samples = []

        start_x = int(np.min(self.table_configuration_corner_nodes[0][:], 0)[0])
        start_y = int(np.min(self.table_configuration_corner_nodes[0][:], 0)[1])

        for x in range(start_x + dialation_radius + 1, self.config.get(Configuration.Dim_X), sampling_distance):
            for y in range(start_y + dialation_radius + 1, self.config.get(Configuration.Dim_Y), sampling_distance):
                if not sample_grid[y, x]:
                    samples.append((x, y))

        return samples

    def get_unoccupied_coordinates(self, ids: list = None) -> np.array:
        # TODO: Function is not used.

        coordinates = np.nonzero(~self.get_merged_occupancy_layers(ids))

        return coordinates

    def remove_occupancy_layer(self, id) -> None:

        self.occupancy_matrices.pop(id)

    def reset_stack(self) -> None:
        self.occupancy_matrices = {}

    def set_occupancy_layer(self, layer_id: str, layer_matrix: np.array) -> None:

        self.occupancy_matrices[layer_id] = layer_matrix

    def draw_ellipse_to_layer(self, layer_id: str, center: tuple, rad_x: int, rad_y: int, rot: float) -> None:

        rr, cc = skimage.draw.ellipse(center[1], center[0], rad_y, rad_x,
                                        shape=(self.config.get(Configuration.Dim_Y), self.config.get(Configuration.Dim_X)), rotation=-rot)
        self.occupancy_matrices[layer_id][rr, cc] = self.config.get(Configuration.Blocked_Space_Value)

    def draw_polygon_to_layer(self, layer_id: str, vertices: list, value=1) -> None:
        """
        The function draws a polygon based on the given vertices. Polygons are only used for visualization.
        """

        lst = list(zip(*vertices))

        vertices_x = lst[0]
        vertices_y = lst[1]

        rr, cc = skimage.draw.polygon(vertices_y, vertices_x,
                                        shape=(self.config.get(Configuration.Dim_Y), self.config.get(Configuration.Dim_X)))

        if value == 0:
            factor = 0
        else:
            factor = self.config.get(Configuration.Blocked_Space_Value) / value

        self.occupancy_matrices[layer_id][rr, cc] = factor
        pass

    def show_table_configuration(self, nodes: bool = False, edges: bool = False, tables: bool = False,
                                stations: bool = False, station_nodes: bool = False, table_configuration: bool = False,
                                boundary: bool = False, medial_axis: bool = False, zones: bool = False,
                                layer_ids: list = None, block: bool = True) -> None:
        """
        Function shows the table configuration.
        """
        handles = []
        plt.figure(figsize=(12, 8))
        if tables:
            # Table corner nodes.
            for index, table in enumerate(self.table_config.tables):
                if index == 0:
                    x, y = zip(*table.table_corner_nodes)
                    # plt.scatter(x, y, c="green", marker=".", label="Module")
                    modules,  = plt.plot([x[0], x[1], x[2], x[3], x[0]], [y[0], y[1], y[2], y[3], y[0]],
                                                        linewidth=1.5, c="green", linestyle="-", label="Module")
                else:
                    x, y = zip(*table.table_corner_nodes)
                    # plt.scatter(x, y, c="green", marker=".")
                    plt.plot([x[0], x[1], x[2], x[3], x[0]], [y[0], y[1], y[2], y[3], y[0]], linewidth=1.5, c="green", linestyle="-")

        if table_configuration:
            # Table configuration corner nodes.
            all_corner_nodes = []
            for corner_nodes in self.table_config.table_configuration_corner_nodes:
                all_corner_nodes.extend(corner_nodes)
            x, y = zip(*all_corner_nodes)
            plt.scatter(x, y, c="green", marker="h", label="table configuration corner nodes")

            # Table configuration corner nodes in cfree.
            all_corner_nodes = []
            for corner_nodes in self.table_config.table_configuration_corner_nodes_cfree:
                all_corner_nodes.extend(corner_nodes)
            x, y = zip(*all_corner_nodes)
            plt.scatter(x, y, c="green", marker="x", label="table configuration corner nodes cfree")

        if boundary:
            # x, y = self.table_config.table_configuration_polygon.exterior.xy
            # table_boundary, = plt.plot(x, y, linewidth=3, marker='', color='green', linestyle='-', label='Grenzelinie Hindernisse')
            # for index in range(len(self.table_config.table_configuration_polygon.interiors)):
            #     x, y = self.table_config.table_configuration_polygon.interiors[index].xy
            #     plt.plot(x, y, linewidth=3, marker='', color='green', linestyle='-')

            x, y = self.table_config.table_configuration_polygon_cfree_round.exterior.xy
            cfree, = plt.plot(x, y, linewidth=3, marker='', color='green', linestyle='--', label='Grenzelinie Freifläche')
            for index in range(len(self.table_config.table_configuration_polygon_cfree_round.interiors)):
                x, y = self.table_config.table_configuration_polygon_cfree_round.interiors[index].xy
                plt.plot(x, y, linewidth=3, marker='', color='green', linestyle='--')

        if edges:
            for index, edge in enumerate(self.node_edge_generator.graph.edges):
                x_coords = (edge.node1.position[0], edge.node2.position[0])
                y_coords = (edge.node1.position[1], edge.node2.position[1])
                # x_coords, y_coords = zip(*edge)
                if index == 0:
                    edges_plot, = plt.plot(x_coords, y_coords, color='blue', linestyle='--', linewidth=1.5, label='Kanten')
                    # plt.arrow(x_coords[0], y_coords[0], (x_coords[1] - x_coords[0])/10, (y_coords[1] - y_coords[0])/10, head_width=5, color='blue', linestyle='--')
                    # plt.arrow(x_coords[1], y_coords[1], (x_coords[0] - x_coords[1])/10, (y_coords[0] - y_coords[1])/10, head_width=5, color='blue', linestyle='--')
                else:
                    plt.plot(x_coords, y_coords, color='blue', linestyle='--', linewidth=1.5)
                    # plt.arrow(x_coords[0], y_coords[0], (x_coords[1] - x_coords[0])/10, (y_coords[1] - y_coords[0])/10, head_width=5, color='blue', linestyle='--')
                    # plt.arrow(x_coords[1], y_coords[1], (x_coords[0] - x_coords[1])/10, (y_coords[0] - y_coords[1])/10, head_width=5, color='blue', linestyle='--')

            # Boundary edges.
            # if boundary:
            # x_coords = []
            # y_coords = []
            # for index, edge in enumerate(self.node_edge_generator.graph.edges):
            #     if edge.boundary_edge:
            #         x_coords = (edge.node1.position[0], edge.node2.position[0])
            #         y_coords = (edge.node1.position[1], edge.node2.position[1])
            #     if index == 0 and x_coords != []:
            #         plt.plot(x_coords, y_coords, c="pink", linestyle='--', linewidth=1.5, label="Außenkanten")
            #     elif x_coords != []:
            #         plt.plot(x_coords, y_coords, c="pink", linestyle='--', linewidth=1.5)

        if nodes:
            x = []
            y = []
            # TODO: Is there a smarter way?
            for sample_point in self.node_edge_generator.graph.nodes:
                x.append(sample_point.position[0])
                y.append(sample_point.position[1])
            # x, y = zip(*self.node_edge_generator.graph.nodes)
            nodes_plot = plt.scatter(x, y, c="blue", marker="x", s=40, zorder=2, label="Knoten")

            # x = []
            # y = []
            # for sample_point in self.node_edge_generator.graph.nodes:
            #     if sample_point.node_type == "buffer":
            #         x.append(sample_point.position[0])
            #         y.append(sample_point.position[1])
            # plt.scatter(x, y, c="yellow", marker="X", s=80, label="sample nodes type")

            # Boundary nodes.
            # if boundary:
            x = []
            y = []
            for sample_point in self.node_edge_generator.graph.nodes:
                if sample_point.boundary_node:
                    x.append(sample_point.position[0])
                    y.append(sample_point.position[1])
            # if x != []:
            #     plt.scatter(x, y, c="pink", marker="X", s=80, zorder=2, label="Außenknoten")

            # Convex corner nodes.
            x = []
            y = []
            for sample_point in self.node_edge_generator.graph.nodes:
                if sample_point.corner_type == "convex":
                    x.append(sample_point.position[0])
                    y.append(sample_point.position[1])
            # if x != []:
            #     nodes_convex_plot = plt.scatter(x, y, c="orange", marker="X", s=80, zorder=2, label="Konvexe Eckknoten")

            # Concave corner nodes.
            x = []
            y = []
            for sample_point in self.node_edge_generator.graph.nodes:
                if sample_point.corner_type == "concave":
                    x.append(sample_point.position[0])
                    y.append(sample_point.position[1])
            # if x != []:
            #     nodes_concave_plot = plt.scatter(x, y, c="green", marker="X", s=80, zorder=2, label="Konkave Eckknoten")

            # Buffer nodes.
            x = []
            y = []
            for sample_point in self.node_edge_generator.graph.nodes:
                if sample_point.node_type == "buffer":  # and sample_point.position != (398, 604) and sample_point.position != (462, 604)
                    x.append(sample_point.position[0])
                    y.append(sample_point.position[1])
            if x != []:
                station_buffer_nodes_plot = plt.scatter(x, y, c="yellow", marker="X", s=80, zorder=2, label="Pufferknoten")

        if stations:
            for index, station in enumerate(self.station_config.stations):
                x, y = zip(*station.station_corner_nodes)
                plt.fill(x, y, color='red')
                # x, y = zip(*station.station_corner_nodes, station.station_corner_nodes[0], station.station_corner_nodes[2], station.station_corner_nodes[3], station.station_corner_nodes[1])  # , station.station_corner_nodes[2], station.station_corner_nodes[3], station.station_corner_nodes[1]
                # if index == 0:
                #     station_plot, = plt.plot(x, y, color='red', linestyle='-', label='Stationen')
                # else:
                #     plt.plot(x, y, color='red', linestyle='-')

        if station_nodes:
            # Connection station node to station trajectory node.
            for index, station in enumerate(self.station_config.stations):
                for station_trajectory_node in station.station_trajectory_nodes:
                    x = [station_trajectory_node[0], station.station_node[0]]
                    y = [station_trajectory_node[1], station.station_node[1]]
                    if index == 0:
                        station_trajectory_plot,  = plt.plot(x, y, linewidth=3, color='blue',
                                                             linestyle='--', label='Anfahrtstrajektorien')
                    else:
                        plt.plot(x, y, linewidth=3, color='blue', linestyle='--')

            # Station nodes.
            x, y = zip(*self.station_config.station_nodes)
            station_nodes_plot = plt.scatter(x, y, c="blue", marker="D", s=60, zorder=2, label="Bearbeitungspositionen")

            # Trajectory nodes.
            x, y = zip(*self.station_config.station_trajectory_nodes)
            station_trajectory_nodes_plot = plt.scatter(x, y, c="red", marker="X", s=80, zorder=2, label="Trajekorienknoten")

            # Buffer nodes.
            # x, y = zip(*self.station_config.station_buffer_nodes)
            # plt.scatter(x, y, c="orange", marker="X", s=100, zorder=2, label="Pufferknoten")

        if medial_axis:
            for index, line in enumerate(self.table_config.medial_axis.geoms):
                if index == 0:
                    x, y = line.xy
                    plt.plot(x, y, marker='', color='black', linestyle='--', linewidth=3, label='Mediale Achse')
                else:
                    x, y = line.xy
                    plt.plot(x, y, marker='', color='black', linestyle='--', linewidth=3)

            # x, y = zip(*self.table_config.medial_axis_nodes)
            # plt.scatter(x, y, c="pink", marker="x", label="medial axis nodes")

            # for medial_axis_edge in self.table_config.medial_axis_edges:
            #     x_coords = (medial_axis_edge[0][0], medial_axis_edge[1][0])
            #     y_coords = (medial_axis_edge[0][1], medial_axis_edge[1][1])
            #     plt.plot(x_coords, y_coords, color='pink', linestyle='--')

        if zones:
            # Colorize the zones.
            # colors_in_legend = set()  # Keep track of which colors are in the legend.
            # for index, polygon in enumerate(self.table_config.zones_polygons):
            #     if self.table_config.zones_directions == []:
            #         break
            #     elif self.table_config.zones_directions[index] == 'right':
            #         color = 'red'
            #         label = 'Zone: rechts'
            #     elif self.table_config.zones_directions[index] == 'left':
            #         color = 'blue'
            #         label = 'Zone: links'
            #     elif self.table_config.zones_directions[index] == 'up':
            #         color = 'green'
            #         label = 'Zone: hoch'
            #     elif self.table_config.zones_directions[index] == 'down':
            #         color = 'yellow'
            #         label = 'Zone: runter'
            #     x, y = polygon.exterior.xy
            #     if color not in colors_in_legend:  # Only add to the legend if this color is not already in it.
            #         plt.fill(x, y, color=color, alpha=0.3, label=label)
            #         colors_in_legend.add(color)  # Add this color to the set of colors in the legend.
            #     else:
            #         plt.fill(x, y, color=color, alpha=0.3)  # Don't add a label if this color is already in the legend.

            # Plot the boundary of the zones.
            # for index, line in enumerate(self.table_config.zones_edges.geoms):
            #     if index == 0:
            #         x, y = line.xy
            #         plt.plot(x, y, marker='o', color='blue', linestyle='--', label='zones edges')
            #     else:
            #         x, y = line.xy
            #         plt.plot(x, y, marker='o', color='blue', linestyle='--')

            # Get a list of colors.
            colors = list(mcolors.CSS4_COLORS.keys())

            # Colorize the zones.
            for index, polygon in enumerate(self.table_config.zones_polygons):
                x, y = polygon.exterior.xy
                plt.fill(x, y, color=colors[index + 10], alpha=0.5)

        # self.add_dilation_difference_layer(value=0.7, kernel_radius=self.config.get(Configuration.Boundary_Distance))
        # self.draw_polygon_to_layer("stations_layer", [(100, 100), (122, 100), (122, 122), (100, 122)], value=0.55)
        plt.imshow(self.get_merged_occupancy_layers(layer_ids), cmap="Greys", origin="lower")  # Blues Greys PuBu
        # plt.imshow(self.get_dialated_occupancy_layers(layer_ids, self.config.get(Configuration.Boundary_Distance)), cmap="Greys", origin="lower")  # Blues

        # Create legend objects
        white_patch = mpatches.Patch(color='white', label='Freifläche')
        silver_patch = mpatches.Patch(color='silver', label='Erweiterte Hindernisse')
        grey_patch = mpatches.Patch(color='grey', label='Dauerhafte Hindernisse')
        red_patch = mpatches.Patch(color='red', label='Stationen')
        black_patch = mpatches.Patch(color='black', label='Temporäre Hindernisse')

        # cbar = plt.colorbar(im)
        # cbar.set_label('Occupancy')
        # cbar.set_ticks([0, 1])
        # cbar.set_ticklabels(['White Area Name', 'Black Area Name'])

        # TODO: Plotting with custom colormap.
        # Define the colors for different regions
        # colors = ["white", "blue", "black"]
        # cmap = mcolors.LinearSegmentedColormap.from_list("", colors)

        # Plot the image with the custom colormap
        # plt.imshow(self.get_merged_occupancy_layers(layer_ids), cmap=cmap, origin="lower")

        plt.xlim(0 - 0.5, self.config.get(Configuration.Dim_X) - 0.5)
        plt.ylim(0 - 0.5, self.config.get(Configuration.Dim_Y) - 0.5)

        fontsize = 14
        plt.xlabel('x [cm]', fontsize=fontsize)
        plt.ylabel('y [cm]', fontsize=fontsize)
        plt.tick_params(axis='both', which='major', labelsize=fontsize)

        fontsize = 16
        plt.rc('axes', labelsize=fontsize)
        plt.rc('xtick', labelsize=fontsize)
        plt.rc('ytick', labelsize=fontsize)
        plt.rc('legend', fontsize=fontsize)

        # # handles.append(grey_patch)
        # # handles.append(silver_patch)
        # # handles.append(white_patch)
        # handles.append(modules)
        # # handles.append(table_boundary)
        # # handles.append(cfree)
        # handles.append(red_patch)
        # handles.append(station_trajectory_plot)
        # handles.append(station_nodes_plot)
        # handles.append(station_trajectory_nodes_plot)
        # handles.append(station_buffer_nodes_plot)
        # # handles.append(nodes_convex_plot)
        # # handles.append(nodes_concave_plot)
        # handles.append(nodes_plot)
        # handles.append(edges_plot)
        # handles.append(black_patch)
        # handles.append(grey_patch)
        # handles.append(silver_patch)
        # plt.legend(handles=handles, loc='upper left')  # best

        # plt.legend(loc='best')  # 'center right' 'best
        plt.show(block=block)
