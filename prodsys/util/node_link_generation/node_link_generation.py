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


def get_all_locations(productionsystem: production_system_data):
    locations = []
    for node in list(productionsystem.resource_data) + list(productionsystem.source_data) + list(productionsystem.sink_data): #list(productionsystem.port_data) + list(productionsystem.resource_data): #get all port locations
        locations.append([node.ID, [x for x in node.location]]) #transform necessary because node link generation works in cm
    return locations

def generate_stations_json(stations: list) -> None:
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
    #TODO: tables mit drawio konfigurieren und tableJSON davon generieren
    #TODO: consider 3d coordinates

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

def mainGenerate(productionsystem: production_system_data):
    min_x, min_y, max_x, max_y = find_borders(productionsystem)
    tableXMax=max(1.1*max_x,50+max_x) #MARKER macht das sinn
    tableYMax=max(1.1*max_y,50+max_y)
    tableXMin=min(1.1*min_x,min_x-50)
    tableYMin=min(1.1*min_y,min_y-50)
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
    items = [
        [loc[1][0]] + [loc[1][1]] + [0] + [0] + ["U"] #Transformation
        for loc in get_all_locations(productionsystem)
    ]
    stations = generate_stations_json(items)

    # Get the dimensions of the production layout.
    dim_x, dim_y = abs(min_x) + abs(max_x), abs(min_y) + abs(max_y)
    # Set the dimensions of the layout.
    config = Configuration()
    config.set(Configuration.Dim_X, int(dim_x))
    config.set(Configuration.Dim_Y, int(dim_y))
    table_config = TableConfiguration(config)
    station_config = StationConfiguration(config, table_config)
    # Add tables and define corner nodes of the table configuration.
    node_edge_generator = NodeEdgeGenerator(config, table_config, station_config)
    node_edge_generator = NodeEdgeGenerator(config, table_config, station_config)
    edge_directionality = EdgeDirectionality(table_config, node_edge_generator)
    visualization = Visualization(config, table_config, station_config, node_edge_generator)
    networkx_formater = format_to_networkx.NetworkXGraphGenerator(node_edge_generator.graph, station_config)
    #vda5050_formater = format_to_vda5050.VDA5050JSONGenerator(node_edge_generator, station_config) #optionally allow 
    #a_star = a_star_algorithm.AStar(table_config, station_config, node_edge_generator, visualization)
    table_config.add_table(tables['corner_nodes'], visualization)
    table_config.generate_table_configuration()

    # Add stations and update table configuration considering the stations.
    station_config.add_stations(stations, visualization)
    table_config.table_configuration_with_stations(station_config)
    #visualization.show_table_configuration(table_configuration=False, boundary=True, stations=True, station_nodes=True)

    # Define the medial axis of the table configuration.    MARKER: Optional
    table_config.define_medial_axis()
    #visualization.show_table_configuration(table_configuration=True, boundary=True, stations=True, station_nodes=True, medial_axis=True)

    # Define zones of the table configuration.  MARKER: Optional
    table_config.define_zones(layout_nr=1) 
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
    distance=100
    min_node_distance = distance #max(0.1*tablesize, 20) #TODO: make min and max distance adapt automatically dependent on the layout size #TODO: sinnvole adaptive distances
    max_node_distance = distance #0.2*tablesize
    node_edge_generator.add_outer_nodes_and_edges(edge_directionality, add_nodes_between=add_nodes_between, max_node_distance=max_node_distance, min_node_distance=min_node_distance, add_edges=add_edges)
    #visualization.show_table_configuration(table_configuration=False, boundary=False, stations=True, station_nodes=True, nodes=True, edges=True)

    # Define random nodes in the free space of the table configuration.
    #node_edge_generator.define_random_nodes(min_node_distance=min_node_distance)    #TODO: choose a grid generation method that is defined here
    node_edge_generator.define_global_grid(grid_spacing=min_node_distance, adjust_spacing=False, add_corner_nodes_first=False)
    #visualization.show_table_configuration(table_configuration=False, boundary=False, stations=True, station_nodes=True, nodes=True, edges=True)

    # Connect nodes by edges using the Delaunay triangulation.
    node_edge_generator.delaunay_triangulation(nodes=node_edge_generator.graph.nodes, without_distance_check=False)
    #visualization.show_table_configuration(table_configuration=False, boundary=False, stations=True, station_nodes=True, nodes=True, edges=True)

    # Define boundary nodes and edges. Nodes with 1 or 2 edges must be removed first.
    edge_directionality.define_boundary_nodes_and_edges()

    # Define boundary edges unidirectional (if possible). Graph connections must be updated afterwards.
    exterior_direction = 'ccw'
    edge_directionality.define_boundary_edges_directionality(exterior_direction=exterior_direction, narrow_sections_unidirectional=False)
    node_edge_generator.graph.update_graph_connections()
    #visualization.show_table_configuration(table_configuration=False, stations=True, station_nodes=False, nodes=True, edges=True)

    # Generate networkx graph. Bidirectional graph and mixed-directional graph are generated.
    # The graph can be visualized. 
    G, DiG = networkx_formater.generate_nx_graph(plot=False) #G: undirected graph, DiG: directed graph
    nodes = {}
    links = []

    #all_locations = get_all_locations(productionsystem)
    all_relevant_resources = [prodres.ID for prodres in get_production_resources(productionsystem)]
    all_relevant_resources.extend([sink.ID for sink in productionsystem.sink_data])
    all_relevant_resources.extend([source.ID for source in productionsystem.source_data])

    all_locations = [(prodres.ID, prodres.location) for prodres in productionsystem.resource_data]
    all_locations.extend([(sink.ID, sink.location) for sink in productionsystem.sink_data])
    all_locations.extend([(source.ID, source.location) for source in productionsystem.source_data])

    # Build a lookup: location -> list of resources
    location_to_resources = {}
    for resource in all_locations:
        if resource[0] in all_relevant_resources:
            key = tuple(resource[1])
            location_to_resources.setdefault(key, []).append(resource)

    location_match_count = {}
    # Map GML node id (int) to matched resource ID
    nx_id_to_resource_id = {}
    new_nodes = [] #nodes that where generated and not previously existing in the production system
    node_blocks = G.nodes
    for block in node_blocks:
        pos = G.nodes[block].get("pos")
        if len(pos) >= 2:
            x = pos[0] 
            y = pos[1] 
        else:
            raise ValueError(f"Node {block} position is not two-dimensional: {pos}")

        matched_id = None
        if pos in location_to_resources:
            count = location_match_count.get(pos, 0)
            resources = location_to_resources[pos]
            if count < len(resources):
                matched_id = resources[count][0]
                location_match_count[pos] = count + 1

        # If no match, fall back to nx node id and add to new nodes
        if not matched_id:
            matched_id = f"node{block}"
            new_nodes.append([matched_id, [x, y]])
        else:
            nx_id_to_resource_id[block] = matched_id

    new_links = []
    edge_blocks = G.edges
    for block in edge_blocks:
        src_id, tgt_id = block[:2]
        if src_id is not None and tgt_id is not None:
            src = nx_id_to_resource_id.get(src_id, f"node{src_id}")
            tgt = nx_id_to_resource_id.get(tgt_id, f"node{tgt_id}")
            new_links.append([src, tgt])
    # Replace node_data in the Prodocutionsystem
    productionsystem.node_data = []
    for node in new_nodes:
        productionsystem.node_data.append(node_data.NodeData(ID=str(node[0]), description="", location=node[1]))

    # Replace links inside LinkTransportProcesses in the Productionsystem
    for LinkTransportProcess in productionsystem.process_data:
        if isinstance(LinkTransportProcess, prodsys.processes_data.LinkTransportProcessData):
            LinkTransportProcess.links = new_links
