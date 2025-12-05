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
        tableXMax=max(1.1*max_x,50+max_x)
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
        # Get the dimensions of the production layout.
        dim_x, dim_y = abs(min_x) + abs(max_x), abs(min_y) + abs(max_y)
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
        dim_x, dim_y = abs(min_x) + abs(max_x), abs(min_y) + abs(max_y)
    
    # Set the dimensions of the layout.
    config = Configuration()
    config.set(Configuration.Dim_X, int(dim_x))
    config.set(Configuration.Dim_Y, int(dim_y))
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
        min_node_distance = tablesize
        max_node_distance = tablesize
    if any(resource.can_move for resource in productionsystem.resource_data if isinstance(resource.control_policy, resource_data.TransportControlPolicy)):
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

    return G

def convert_nx_to_prodsys(adapter: production_system_data, G: nx.Graph):

    #all_locations = get_all_locations(productionsystem)
    #all_relevant_resources = [prodres.ID for prodres in get_production_resources(productionsystem)]
    #all_relevant_resources.extend([sink.ID for sink in productionsystem.sink_data])
    #all_relevant_resources.extend([source.ID for source in productionsystem.source_data])

    all_locations = [(prodres.ID, prodres.location) for prodres in get_production_resources(adapter)]
    all_locations.extend([(sink.ID, sink.location) for sink in adapter.sink_data])
    all_locations.extend([(source.ID, source.location) for source in adapter.source_data])

    # Build a lookup: location -> list of resources
    location_to_resources = {}
    for resource in all_locations:
        key = tuple(resource[1])
        location_to_resources.setdefault(key, []).append(resource[0])

    nx_to_location = {}
    # Map GML node id (int) to matched resource ID
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
        if pos not in location_to_resources:
            new_nodes.append([f"node_{block}", (x, y)])


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
            tgt = f"node_{tgt_id}"
            for src_resource in location_to_resources[src_loc]:
                new_links.append([src_resource, tgt])
        elif tgt_loc in location_to_resources:
            src = f"node_{src_id}"
            for tgt_resource in location_to_resources[tgt_loc]:
                new_links.append([src, tgt_resource])                
        else:
            src = f"node_{src_id}"
            tgt = f"node_{tgt_id}"
            new_links.append([src, tgt])

    return new_nodes, new_links

def apply_nodes_links(adapter: production_system_data, nodes, links) -> None:

    
    # Replace node_data in the Prodocutionsystem
    adapter.node_data = []
    for node in nodes:
        adapter.node_data.append(node_data.NodeData(ID=str(node[0]), description="", location=node[1]))

    # Replace links inside LinkTransportProcesses in the Productionsystem
    for LinkTransportProcess in adapter.process_data:
        if isinstance(LinkTransportProcess, prodsys.processes_data.LinkTransportProcessData):
            LinkTransportProcess.links = links

def generate_and_apply_network(adapter: production_system_data, xml_path = None, visualize=False, style="grid", simple_connection=True) -> None:
    if xml_path:
        tables = parse_drawio_rectangles(xml_path)
    else:
        tables = None
    G = generator(adapter, tables, visualize=visualize, style=style, simple_connection=simple_connection)
    nodes, links = convert_nx_to_prodsys(adapter, G)
    apply_nodes_links(adapter, nodes, links)

def get_new_links(adapter: production_system_data, style="grid") -> List[Tuple[str, str]]:
    G = generator(adapter, style=style)
    _, new_links = convert_nx_to_prodsys(adapter, G)
    return new_links