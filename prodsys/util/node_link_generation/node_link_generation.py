import prodsys
from prodsys.models import production_system_data, resource_data, sink_data, source_data, node_data, port_data
from prodsys.models.production_system_data import get_production_resources
from prodsys.util.node_link_generation.table_configuration import TableConfiguration
from prodsys.util.node_link_generation.table_configuration import StationConfiguration
from prodsys.util.node_link_generation.table_configuration import Visualization
from prodsys.util.node_link_generation.table_configuration_nodes_edges import NodeEdgeGenerator
from prodsys.util.node_link_generation.edge_directionality import EdgeDirectionality 
from prodsys.util.node_link_generation.configuration import Configuration 
#import a_star_algorithm 
import networkx as nx
import prodsys.util.node_link_generation.format_to_networkx as format_to_networkx
from typing import List, Any, Set, Optional, Tuple, Union
import xml.etree.ElementTree as ET

def parse_drawio_rectangles(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    tables = []

    # Find all mxCell elements with vertex="1"
    for cell in root.iter("mxCell"):
        if cell.get("vertex") != "1":
            continue

        # Identify rotation -> reject non-zero (draw.io writes e.g. rotation=45)
        style = cell.get("style", "")
        # draw.io stores rotation as "rotation=xx"
        rotation = None
        for part in style.split(";"):
            if part.startswith("rotation="):
                rotation = float(part.split("=")[1])
        if rotation not in (None, 0):
            raise ValueError(f"Non-right-angle rotation detected in cell {cell.get('id')}.")

        geom = cell.find("mxGeometry")
        if geom is None:
            continue  # useless entry

        # draw.io omits coordinates if they're zero; default to 0
        x = float(geom.get("x", 0))
        y = float(geom.get("y", 0))
        w = float(geom.get("width", 0))
        h = float(geom.get("height", 0))

        # compute rectangle corner points
        tableXMin = x
        tableYMin = y
        tableXMax = x + w
        tableYMax = y + h

        rectangle = {
            "corner_nodes": [
                {"pose": [tableXMin, tableYMin, 0]},
                {"pose": [tableXMax, tableYMin, 0]},
                {"pose": [tableXMax, tableYMax, 0]},
                {"pose": [tableXMin, tableYMax, 0]},
            ],
            "center_node": [
                {"pose": [
                    (tableXMin + tableXMax) / 2,
                    (tableYMin + tableYMax) / 2,
                    0,
                ]}
            ]
        }

        tables.append(rectangle)

    return tables

def get_all_locations(productionsystem: production_system_data):
    locations = []
    for node in list(productionsystem.resource_data) + list(productionsystem.source_data) + list(productionsystem.sink_data): #list(productionsystem.port_data) + list(productionsystem.resource_data): #get all port locations
        locations.append([node.ID, [x for x in node.location]])
    return locations

def generate_stations_config(stations: list) -> None:
    """
    Function is used to generate a JSON file for the station configuration.
    """
    # Prepare the new data structure.
    new_data = {
        "physical_objects": [],
    }
    Trajectory_Node_Distance = 0
    # Convert the original data into the new format.
    for station in stations:
        # Unidirectional station. Has one trajectory node. In and out port are at the same side.
        # Pose is the center of the station defined by the bounding box.
        if station[4] == "U":
            station_data = {
                "base": "if2",
                "pose": [station[0], station[1], station[2]],
                "bounding_box": [[-station[3]/2, -station[3]/2, 0], [station[3]/2, station[3]/2, 0]],
                "poi": {"in_port.trajectory_node": [station[3]/2 + Trajectory_Node_Distance, 0, 0],
                        "out_port.trajectory_node": [station[3]/2 + Trajectory_Node_Distance, 0, 0]},
                "urdf_file": {
                    "_comment": "just an example, not correct file!!",
                    "urdf_file_url": "https://backend.fac6310.btia.emea.ide.rb/cadfiles/ClipsCover/MO_0037_Press_EPSdp/MO_0037_Press_EPSdp.obj"
                }
            }
        elif station[4] == "B":
            # Bidirectional station. Has two trajectory nodes. In and out port are at the opposite sides.
            # Pose is in the center of the station defined by the bounding box.
            station_data = {
                "base": "if2",
                "pose": [station[0], station[1], station[2]],
                "bounding_box": [[-station[3]/2, -station[3]/2, 0],
                                    [station[3]/2, station[3]/2, 0]],
                "poi": {"in_port.trajectory_node": [station[3]/2 + Trajectory_Node_Distance, 0, 0],
                        "out_port.trajectory_node": [-station[3]/2 - Trajectory_Node_Distance, 0, 0]},
                "urdf_file": {
                    "_comment": "just an example, not correct file!!",
                    "urdf_file_url": "https://backend.fac6310.btia.emea.ide.rb/cadfiles/ClipsCover/MO_0037_Press_EPSdp/MO_0037_Press_EPSdp.obj"
                }
            }
        new_data["physical_objects"].append(station_data)

    return new_data

def find_borders(productionsystem: production_system_data):
    #finds the area within all stations are located

    stations = get_all_locations(productionsystem)
    max_x, max_y, = stations[0][1]
    min_x, min_y = stations[0][1]
    for station in stations: #get the max x and y coordinates of the stations to determine the size of the table layout
        if station[1][0] > max_x:
            max_x = station[1][0]
        if station[1][1] > max_y:
            max_y = station[1][1]
        if station[1][0] < min_x:
            min_x = station[1][0]
        if station[1][1] < min_y:
            min_y = station[1][1]
    return min_x, min_y, max_x, max_y

def generator(productionsystem: production_system_data, area=None, visualize=False, style="grid", simple_connection=True) -> nx.Graph:
    # Generate tables and stations based on the production system layout.
    items = [
        [loc[1][0]] + [loc[1][1]] + [0] + [0] + ["U"]
        for loc in get_all_locations(productionsystem)
    ]
    stations = generate_stations_config(items)
    # Determine table configuration based on area or production system layout.
    if area is None:
        min_x, min_y, max_x, max_y = find_borders(productionsystem)
        # Calculate proportional margins based on production system size
        # Use 10% of range, but clamp between 1.0 and 10.0 units
        range_x = max_x - min_x
        range_y = max_y - min_y
        margin_x = max(range_x * 0.1, 1.0)
        margin_x = min(margin_x, 10.0)
        margin_y = max(range_y * 0.1, 1.0)
        margin_y = min(margin_y, 10.0)
        
        tableXMax = max_x + margin_x
        tableYMax = max_y + margin_y
        tableXMin = min_x - margin_x
        tableYMin = min_y - margin_y
        tables = {
            "corner_nodes": [
                {"pose": [tableXMin, tableYMin, 0]}, 
                {"pose": [tableXMax, tableYMin, 0]},
                {"pose": [tableXMax, tableYMax, 0]},
                {"pose": [tableXMin, tableYMax, 0]}
            ],
            "center_node": [
                {"pose": [((tableXMin + tableXMax)/2), ((tableYMin + tableYMax)/2), 0]}
            ]
        }
        # Get the dimensions of the TABLE layout (after adding margins), not the production system
        # This is important for calculating proper node spacing
        table_dim_x = tableXMax - tableXMin
        table_dim_y = tableYMax - tableYMin
        dim_x, dim_y = table_dim_x, table_dim_y
    else:
        tables = area
        min_x, min_y, _ = tables[0]['corner_nodes'][0]['pose']
        max_x, max_y, _ = tables[0]['corner_nodes'][0]['pose']
    
        for table in tables:
            for corner in table['corner_nodes']:
                if corner['pose'][0] > max_x:
                    max_x = corner['pose'][0]
                if corner['pose'][1] > max_y:
                    max_y = corner['pose'][1]
                if corner['pose'][0] < min_x:
                    min_x = corner['pose'][0]
                if corner['pose'][1] < min_y:
                    min_y = corner['pose'][1]
        # Get the dimensions of the table layout (correct calculation: range, not sum of absolutes)
        dim_x, dim_y = max_x - min_x, max_y - min_y
    
    # Set the dimensions of the layout.
    config = Configuration()
    config.set(Configuration.Dim_X, int(dim_x))
    config.set(Configuration.Dim_Y, int(dim_y))
    
    # CRITICAL FIX: Make hardcoded boundary/distance values proportional to table size
    # The default values (32, 24, 16) are designed for large tables (~100x50 units)
    # For small tables, these values prevent node generation. Scale them DOWN only for small tables.
    tablesize = min(dim_x, dim_y)
    
    # Store original values to restore later (Configuration is a singleton)
    original_min_node_dist = config.get(Configuration.Min_Node_Distance)
    original_min_edge_dist = config.get(Configuration.Min_Node_Edge_Distance)
    original_trajectory_dist = config.get(Configuration.Trajectory_Node_Distance)
    original_buffer_dist = config.get(Configuration.Buffer_Node_Distance)
    
    # Only scale DOWN for small tables (< 50 units). For large tables, use original values.
    # The original values work fine for large systems, but are too large for small systems.
    if tablesize < 50.0:
        # Scale down proportionally for small tables, but don't go below minimums
        scale_factor = max(tablesize / 50.0, 0.1)  # Scale based on 50 units as reference, minimum 0.1
        
        scaled_min_node_dist = max(int(original_min_node_dist * scale_factor), 1)  # At least 1 unit
        scaled_min_edge_dist = max(int(original_min_edge_dist * scale_factor), 1)
        scaled_trajectory_dist = max(int(original_trajectory_dist * scale_factor), 1)
        scaled_buffer_dist = max(int(original_buffer_dist * scale_factor), 1)
        
        config.set(Configuration.Min_Node_Distance, scaled_min_node_dist)
        config.set(Configuration.Min_Node_Edge_Distance, scaled_min_edge_dist)
        config.set(Configuration.Trajectory_Node_Distance, scaled_trajectory_dist)
        config.set(Configuration.Buffer_Node_Distance, scaled_buffer_dist)
    # For large tables (>= 50 units), keep original values - no scaling needed
    
    table_config = TableConfiguration(config)
    station_config = StationConfiguration(config, table_config)
    # Add tables and define corner nodes of the table configuration.
    node_edge_generator = NodeEdgeGenerator(config, table_config, station_config)
    edge_directionality = EdgeDirectionality(table_config, node_edge_generator)
    visualization = Visualization(config, table_config, station_config, node_edge_generator)
    networkx_formater = format_to_networkx.NetworkXGraphGenerator(node_edge_generator.graph, station_config)
    #vda5050_formater = format_to_vda5050.VDA5050JSONGenerator(node_edge_generator, station_config) #optionally allow 
    #a_star = a_star_algorithm.AStar(table_config, station_config, node_edge_generator, visualization)
    if isinstance(tables, list):
        for table in tables:  # in case of multiple tables
            table_config.add_table(table['corner_nodes'], visualization)
    else:
        table_config.add_table(tables['corner_nodes'], visualization)
    table_config.generate_table_configuration()

    # Add stations and update table configuration considering the stations.
    station_config.add_stations(stations, visualization)
    table_config.table_configuration_with_stations(station_config)
    #visualization.show_table_configuration(table_configuration=False, boundary=True, stations=True, station_nodes=True)

    # Define the medial axis of the table configuration.    MARKER: Optional
    if not simple_connection:    
        table_config.define_medial_axis()
    #visualization.show_table_configuration(table_configuration=True, boundary=True, stations=True, station_nodes=True, medial_axis=True)

    # Define zones of the table configuration.  MARKER: Optional
    if not simple_connection:
        table_config.define_zones()
    #visualization.show_table_configuration(table_configuration=True, boundary=True, stations=False, station_nodes=False, zones=True)

    # Define station nodes and edges. Add edges optionally.
    # Variable is defined, so it is consistent with functions called afterwards.
    # Station nodes (and edges) must be added before other nodes are added. Here only trajectory nodes are defined.
    add_edges = False
    node_edge_generator.add_station_nodes_and_edges(add_edges=add_edges, buffer_nodes=False) #this method is also used in add_outer_nodes_and_edges
    #visualization.show_table_configuration(table_configuration=False, boundary=False, stations=True, station_nodes=True, nodes=True, edges=True)

    # Add nodes (and edges) along the boundary of table configuration considering stations.
    # Intermediate nodes along the boundary edges can be added optionally. The minimum distance between nodes can be defined.
    add_nodes_between = True
    tablesize = min(dim_x, dim_y)

    if not simple_connection:
        min_node_distance = max(0.1*tablesize, 10)
        max_node_distance = 0.2*tablesize
    else:
        # For simple_connection, use proportional spacing but ensure enough nodes are generated
        # For very small tables (< 10 units), use a fixed small spacing to ensure multiple nodes
        # For larger tables, use proportional spacing
        if tablesize < 10.0:
            # Use spacing that ensures at least 4-5 nodes fit in each dimension
            min_node_distance = max(tablesize / 5.0, 0.3)  # At least 0.3, but aim for 5 nodes per dimension
            max_node_distance = max(tablesize / 4.0, 0.5)   # At least 0.5, but aim for 4 nodes per dimension
        else:
            min_node_distance = max(0.1*tablesize, 0.5)  # At least 0.5 units, typically 10% of table size
            max_node_distance = max(0.15*tablesize, 1.0)  # At least 1.0 units, typically 15% of table size
    # Check if we need to add outer nodes: either resources can move, or there are LinkTransportProcesses
    has_movable_resources = any(resource.can_move for resource in productionsystem.resource_data if isinstance(resource.control_policy, resource_data.TransportControlPolicy))
    # Check for LinkTransportProcessData - need to import it
    from prodsys.models import processes_data
    has_link_transport = any(isinstance(process, processes_data.LinkTransportProcessData) for process in productionsystem.process_data)
    
    if has_movable_resources or has_link_transport:
        node_edge_generator.add_outer_nodes_and_edges(edge_directionality, add_nodes_between=add_nodes_between, max_node_distance=max_node_distance, min_node_distance=min_node_distance, add_edges=add_edges)
    #visualization.show_table_configuration(table_configuration=False, boundary=False, stations=True, station_nodes=True, nodes=True, edges=True)

    # Define random nodes in the free space of the table configuration.
    # choose a grid generation method that is defined here
    if style == "grid":
        node_edge_generator.define_global_grid(grid_spacing=min_node_distance, adjust_spacing=False, add_corner_nodes_first=False)
    elif style == "random":
        node_edge_generator.define_random_nodes(min_node_distance=min_node_distance)
    #visualization.show_table_configuration(table_configuration=False, boundary=False, stations=True, station_nodes=True, nodes=True, edges=True)

    # Connect nodes by edges using the Delaunay triangulation.
    # Check if we have enough nodes (need at least 4 for Delaunay triangulation)
    num_nodes = len(node_edge_generator.graph.nodes)
    smaller_spacing = min_node_distance  # Initialize for error message
    if num_nodes < 4:
        # If we don't have enough nodes, try generating with progressively smaller spacing
        # This can happen with very small tables or when grid generation filters out too many nodes
        for attempt in range(3):  # Try up to 3 times with smaller spacing
            smaller_spacing = min_node_distance / (2 ** (attempt + 1))
            smaller_spacing = max(smaller_spacing, 0.1)  # Don't go below 0.1 units
            if style == "grid":
                node_edge_generator.define_global_grid(grid_spacing=smaller_spacing, adjust_spacing=False, add_corner_nodes_first=False)
            elif style == "random":
                node_edge_generator.define_random_nodes(min_node_distance=smaller_spacing)
            num_nodes = len(node_edge_generator.graph.nodes)
            if num_nodes >= 4:
                break
    
    if num_nodes < 4:
        # Last resort: try with very small fixed spacing
        if num_nodes < 4:
            very_small_spacing = 0.2  # Very small fixed spacing
            if style == "grid":
                node_edge_generator.define_global_grid(grid_spacing=very_small_spacing, adjust_spacing=True, add_corner_nodes_first=True)
            elif style == "random":
                node_edge_generator.define_random_nodes(min_node_distance=very_small_spacing)
            num_nodes = len(node_edge_generator.graph.nodes)
    
    if num_nodes < 4:
        raise ValueError(f"Not enough nodes generated ({num_nodes}) for Delaunay triangulation (need at least 4). "
                        f"Table size: {tablesize:.2f}, initial spacing: {min_node_distance:.2f}, final spacing tried: {smaller_spacing:.2f}. "
                        f"This may indicate an issue with the table configuration or node generation algorithm. "
                        f"Table bounds: X=[{tableXMin if 'tableXMin' in locals() else 'N/A':.2f}, {tableXMax if 'tableXMax' in locals() else 'N/A':.2f}], "
                        f"Y=[{tableYMin if 'tableYMin' in locals() else 'N/A':.2f}, {tableYMax if 'tableYMax' in locals() else 'N/A':.2f}]. "
                        f"Try using a larger table area, different style ('random' instead of 'grid'), or disabling simple_connection.")
    
    node_edge_generator.delaunay_triangulation(nodes=node_edge_generator.graph.nodes, without_distance_check=False)
    #visualization.show_table_configuration(table_configuration=False, boundary=False, stations=True, station_nodes=True, nodes=True, edges=True)

    # Define boundary nodes and edges. Nodes with 1 or 2 edges must be removed first.
    edge_directionality.define_boundary_nodes_and_edges()

    # Define boundary edges unidirectional (if possible). Graph connections must be updated afterwards.
    exterior_direction = 'ccw'
    edge_directionality.define_boundary_edges_directionality(exterior_direction=exterior_direction, narrow_sections_unidirectional=False)
    node_edge_generator.graph.update_graph_connections()
    if visualize:
        visualization.show_table_configuration(table_configuration=False, stations=True, station_nodes=False, nodes=True, edges=True)

    # Generate networkx graph. Bidirectional graph and mixed-directional graph are generated.
    # The graph can be visualized. 
    G, DiG = networkx_formater.generate_nx_graph(plot=False) #G: undirected graph, DiG: directed graph

    # Restore original Configuration values (Configuration is a singleton, so we need to restore)
    # to prevent test pollution when tests run in sequence
    if tablesize < 50.0:
        config.set(Configuration.Min_Node_Distance, original_min_node_dist)
        config.set(Configuration.Min_Node_Edge_Distance, original_min_edge_dist)
        config.set(Configuration.Trajectory_Node_Distance, original_trajectory_dist)
        config.set(Configuration.Buffer_Node_Distance, original_buffer_dist)

    return G

def convert_nx_to_prodsys(adapter: production_system_data, G: nx.Graph):

    #all_locations = get_all_locations(productionsystem)
    #all_relevant_resources = [prodres.ID for prodres in get_production_resources(productionsystem)]
    #all_relevant_resources.extend([sink.ID for sink in productionsystem.sink_data])
    #all_relevant_resources.extend([source.ID for source in productionsystem.source_data])

    # Include ALL resources (production + transport), not just production resources
    # This ensures transport resources like Workers_Part1 are also included in the network
    from prodsys.models.production_system_data import get_transport_resources
    all_locations = [(prodres.ID, prodres.location) for prodres in get_production_resources(adapter)]
    all_locations.extend([(tres.ID, tres.location) for tres in get_transport_resources(adapter)])
    all_locations.extend([(sink.ID, sink.location) for sink in adapter.sink_data])
    all_locations.extend([(source.ID, source.location) for source in adapter.source_data])

    # Build a lookup: location -> list of resources
    location_to_resources = {}
    for resource in all_locations:
        key = tuple(resource[1])
        location_to_resources.setdefault(key, []).append(resource[0])

    nx_to_location = {}
    # Map GML node id (int) to matched resource ID
    # Also track which nodes will be added to node_data (for validation)
    node_id_to_name = {}  # Maps NetworkX node ID -> node name that will be in node_data
    new_nodes = [] #nodes that where generated and not previously existing in the production system
    node_blocks = G.nodes
    for block in node_blocks: #extract the newly generated nodes from the networkx graph
        pos = G.nodes[block].get("pos")
        if len(pos) >= 2:
            x = pos[0] 
            y = pos[1] 
        else:
            raise ValueError(f"Node {block} position is not two-dimensional: {pos}") #Generator can only handle 2D positions

        nx_to_location[block] = pos
        node_name = f"node_{block}"
        if pos not in location_to_resources:
            # This node will be added to node_data
            new_nodes.append([node_name, (x, y)])
            node_id_to_name[block] = node_name
        else:
            # This node is at a resource location, so it won't be added as a separate node
            # But we still need to track it for linking purposes
            # In this case, links should use the resource ID, not the node ID
            node_id_to_name[block] = None  # Mark as not a separate node


    new_links = []
    edge_blocks = G.edges
    for block in edge_blocks:
        src_id, tgt_id = block[:2]
        src_loc, tgt_loc = nx_to_location[src_id], nx_to_location[tgt_id]
        if src_loc in location_to_resources and tgt_loc in location_to_resources:
            for src_resource in location_to_resources[src_loc]:
                for tgt_resource in location_to_resources[tgt_loc]:
                    new_links.append([src_resource, tgt_resource])
        elif src_loc in location_to_resources:
            # Source is a resource, target might be a node or resource
            if tgt_loc in location_to_resources:
                # Both are resources - should have been handled above
                pass
            else:
                # Target is a node - use node name if it will be in node_data
                tgt_name = node_id_to_name.get(tgt_id)
                if tgt_name:
                    for src_resource in location_to_resources[src_loc]:
                        new_links.append([src_resource, tgt_name])
                # If tgt_name is None, the node is at a resource location, so we should link to that resource
                if not tgt_name and tgt_loc in location_to_resources:
                    for src_resource in location_to_resources[src_loc]:
                        for tgt_resource in location_to_resources[tgt_loc]:
                            new_links.append([src_resource, tgt_resource])
        elif tgt_loc in location_to_resources:
            # Target is a resource, source might be a node or resource
            src_name = node_id_to_name.get(src_id)
            if src_name:
                for tgt_resource in location_to_resources[tgt_loc]:
                    new_links.append([src_name, tgt_resource])
            # If src_name is None, the node is at a resource location, so we should link to that resource
            if not src_name and src_loc in location_to_resources:
                for src_resource in location_to_resources[src_loc]:
                    for tgt_resource in location_to_resources[tgt_loc]:
                        new_links.append([src_resource, tgt_resource])
        else:
            # Both are nodes - create links appropriately
            src_name = node_id_to_name.get(src_id)
            tgt_name = node_id_to_name.get(tgt_id)
            
            if src_name and tgt_name:
                # Both nodes will be in node_data
                new_links.append([src_name, tgt_name])
            elif src_name and not tgt_name:
                # Source is a node, target is at a resource location
                if tgt_loc in location_to_resources:
                    for tgt_resource in location_to_resources[tgt_loc]:
                        new_links.append([src_name, tgt_resource])
            elif not src_name and tgt_name:
                # Source is at a resource location, target is a node
                if src_loc in location_to_resources:
                    for src_resource in location_to_resources[src_loc]:
                        new_links.append([src_resource, tgt_name])
            elif not src_name and not tgt_name:
                # Both nodes are at resource locations - link the resources
                if src_loc in location_to_resources and tgt_loc in location_to_resources:
                    for src_resource in location_to_resources[src_loc]:
                        for tgt_resource in location_to_resources[tgt_loc]:
                            new_links.append([src_resource, tgt_resource])

    # CRITICAL FIX: Ensure ALL resources/sources/sinks are connected
    # Some stations may not get nodes in the graph due to station configuration limitations
    # Connect any unconnected resources to the nearest node in the graph
    connected_resources = set()
    for link in new_links:
        connected_resources.add(link[0])
        connected_resources.add(link[1])
    
    # Find resources that aren't connected
    all_resource_ids = {r[0] for r in all_locations}
    unconnected_resources = {rid for rid in all_resource_ids if rid not in connected_resources}
    
    if unconnected_resources and nx_to_location:
        # Helper function to find nearest node
        def find_nearest_node_id(resource_loc):
            """Find the ID of the nearest node to the given location."""
            min_dist = float('inf')
            nearest_id = None
            for node_id, node_loc in nx_to_location.items():
                if len(node_loc) >= 2 and len(resource_loc) >= 2:
                    dx = node_loc[0] - resource_loc[0]
                    dy = node_loc[1] - resource_loc[1]
                    dist = (dx*dx + dy*dy) ** 0.5
                    if dist < min_dist:
                        min_dist = dist
                        nearest_id = node_id
            return nearest_id
        
        # Connect each unconnected resource to its nearest connected location
        # IMPORTANT: Only create links with IDs that will be valid (in node_data, resource_data, etc.)
        for resource_id in unconnected_resources:
            resource_loc = next((r[1] for r in all_locations if r[0] == resource_id), None)
            if resource_loc:
                # Find nearest connected resource first (preferred)
                nearest_connected_resource = None
                min_dist_to_resource = float('inf')
                for link in new_links:
                    for target in [link[0], link[1]]:
                        if target in all_resource_ids and target in connected_resources:
                            target_loc = next((r[1] for r in all_locations if r[0] == target), None)
                            if target_loc and len(target_loc) >= 2 and len(resource_loc) >= 2:
                                dx = target_loc[0] - resource_loc[0]
                                dy = target_loc[1] - resource_loc[1]
                                dist = (dx*dx + dy*dy) ** 0.5
                                if dist < min_dist_to_resource:
                                    min_dist_to_resource = dist
                                    nearest_connected_resource = target
                
                # If we found a connected resource, link to it
                if nearest_connected_resource:
                    new_links.append([resource_id, nearest_connected_resource])
                    new_links.append([nearest_connected_resource, resource_id])
                else:
                    # Fallback: find nearest node that will be in node_data
                    nearest_node_id = find_nearest_node_id(resource_loc)
                    if nearest_node_id is not None:
                        nearest_node_name = node_id_to_name.get(nearest_node_id)
                        if nearest_node_name:
                            # Node will be in node_data, so we can link to it
                            new_links.append([resource_id, nearest_node_name])
                            new_links.append([nearest_node_name, resource_id])
                        else:
                            # Node is at a resource location - link to that resource instead
                            nearest_node_loc = nx_to_location.get(nearest_node_id)
                            if nearest_node_loc and tuple(nearest_node_loc) in location_to_resources:
                                nearest_resource = location_to_resources[tuple(nearest_node_loc)][0]
                                if nearest_resource in connected_resources:
                                    new_links.append([resource_id, nearest_resource])
                                    new_links.append([nearest_resource, resource_id])

    return new_nodes, new_links

def apply_nodes_links(adapter: production_system_data, nodes, links) -> None:

    
    # Replace node_data in the Prodocutionsystem
    adapter.node_data = []
    for node in nodes:
        adapter.node_data.append(node_data.NodeData(ID=str(node[0]), description="", location=node[1]))

    # Replace links inside LinkTransportProcesses in the Productionsystem
    # Update links for ALL LinkTransportProcesses to ensure old links are cleared
    # For conveyors (can_move=False), we update all of them to handle multiple conveyor processes
    for LinkTransportProcess in adapter.process_data:
        if isinstance(LinkTransportProcess, prodsys.processes_data.LinkTransportProcessData):
            # Update links for all processes to clear any old/stale links
            LinkTransportProcess.links = links
            # Note: Original code broke after first conveyor, but we now update all conveyors
            # to handle cases with multiple conveyor processes in evolutionary algorithm

def generate_and_apply_network(adapter: production_system_data, xml_path = None, visualize=False, style="grid", simple_connection=True) -> None:
    if xml_path:
        tables = parse_drawio_rectangles(xml_path)
    else:
        tables = None
    G = generator(adapter, tables, visualize=visualize, style=style, simple_connection=simple_connection)
    nodes, links = convert_nx_to_prodsys(adapter, G)
    apply_nodes_links(adapter, nodes, links)

def get_new_links(adapter: production_system_data, style="grid", simple_connection=True) -> List[Tuple[str, str]]:
    G = generator(adapter, style=style, simple_connection=simple_connection)
    _, new_links = convert_nx_to_prodsys(adapter, G)
    return new_links