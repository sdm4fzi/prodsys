import prodsys
from prodsys.models import production_system_data, resource_data, sink_data, source_data, node_data, port_data
from typing import List, Any, Set, Optional, Tuple, Union
import json

def get_io_locations( 
    locatable: Union[
        resource_data.ResourceData,
        source_data.SourceData,
        sink_data.SinkData,
        port_data.StoreData,
    ],
) -> List[List[float]]:
    locations = []
    if (
        hasattr(locatable, "input_location")
        and locatable.input_location != locatable.location
    ):
        locations.append(locatable.input_location)
    else:
        locations.append(locatable.location)
    if (
        hasattr(locatable, "output_location")
        and locatable.output_location != locatable.location
    ):
        locations.append(locatable.output_location)
    return locations

def get_all_locations(productionsystem: production_system_data):
    locations = []
    for node in productionsystem.resource_data, productionsystem.source_data, productionsystem.sink_data, productionsystem.port_data:
        locations.append(get_io_locations(node))
        for location in locations:
            coord = (node.ID, location)
            locations.append(coord)    
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

    # Save all stations in a single JSON file.
    with open('NodeEdgeNetworkGeneration/input_files/stations.json', 'w') as f:
        json.dump(new_data, f, indent=4)

def find_borders(productionsystem: production_system_data):
    #finds the area within all stations are located
    #TODO: tables mit drawio konfigurieren und tableJSON davon generieren
    #TODO: consider 3d coordinates

    stations = get_all_locations(productionsystem)
    max_x, max_y, = stations[0, 0]
    min_x, min_y = stations[0, 0]
    for station in stations: #get the max x and y coordinates of the stations to determine the size of the table layout
        if station[0] > max_x:
            max_x = station[0] 
        if station[1] > max_y:
            max_y = station[1]
        if station[0] < min_x:
            min_x = station[0]
        if station[1] < min_y:
            min_y = station[1]
    tables = [[0,0,0]]
    return min_x, min_y, max_x, max_y

def mainGenerate(productionsystem: production_system_data):
    
    min_x, min_y, max_x, max_y = find_borders(productionsystem)
    tableXMax=max(1.1*max_x,50+max_x) #MARKER macht das sinn
    tableYMax=max(1.1*max_y,50+max_y)
    tableXMin=min(1.1*min_x,min_x-50)
    tableYMin=min(1.1*min_y,min_y-50)
    table_data = {
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
    with open('/tables.json', 'w') as f:
        json.dump(table_data, f, indent=4) #MARKER Brauchts umbedingt diese json?

    generate_stations_json(stations)

    # Load the tables from the JSON file.
    with open('NodeEdgeNetworkGeneration/input_files/tables.json', 'r') as f:  # open('NodeEdgeNetworkGeneration/input_files/track_modules_layout_rotated.json', 'r') as f:
        tables = json.load(f)
    # Load the stations from the JSON file.
    with open('NodeEdgeNetworkGeneration/input_files/stations.json', 'r') as f:  
        stations = json.load(f)

    # Get the dimensions of the production layout.
    dim_x, dim_y = abs(min_x) + abs(max_x), abs(min_y) + abs(max_y)
    # Set the dimensions of the layout.
    config = Configuration()
    config.set(Configuration.Dim_X, dim_x)
    config.set(Configuration.Dim_Y, dim_y)
    
    # Add tables and define corner nodes of the table configuration.
    from table_configuration import TableConfiguration
    from table_configuration import StationConfiguration
    from table_configuration import Visualization
    from table_configuration_nodes_edges import NodeEdgeGenerator
    from edge_directionality import EdgeDirectionality # type: ignore
    import a_star_algorithm # type: ignore
    import networkx as nx

    node_edge_generator = NodeEdgeGenerator(config, table_config, station_config)

    config = Configuration()
    table_config = TableConfiguration(config)
    station_config = StationConfiguration(config, table_config)
    node_edge_generator = NodeEdgeGenerator(config, table_config, station_config)
    edge_directionality = EdgeDirectionality(table_config, node_edge_generator)
    visualization = Visualization(config, table_config, station_config, node_edge_generator)
    networkx_formater = format_to_networkx.NetworkXGraphGenerator(node_edge_generator.graph, station_config)
    vda5050_formater = format_to_vda5050.VDA5050JSONGenerator(node_edge_generator, station_config) #optionally allow 
    a_star = a_star_algorithm.AStar(table_config, station_config, node_edge_generator, visualization)
    for table in tables:
        table_config.add_table(table['corner_nodes'], visualization)
    table_config.generate_table_configuration()










#Classes from Marvin Ruedt

class Configuration: # Singleton class to store configuration parameters for node and link generation.
    _instance = None

    Boundary_Distance = 'boundary-distance'
    Min_Node_Distance = 'min-node-distance'
    Min_Node_Edge_Distance = 'min-node-edge-distance'
    Trajectory_Node_Distance = 'trajectory-node-distance'
    Buffer_Node_Distance = 'buffer-node-distance'
    Dim_X = 'dim-x'
    Dim_Y = 'dim-y'
    Dim_Table_X = 'dim-table-x'
    Dim_Table_Y = 'dim-table-y'
    Blocked_Space_Value = 'blocked-space-value'

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Configuration, cls).__new__(cls)
        return cls._instance

    def __init__(self, dim_x=None, dim_y=None):
        """
        Only one instance of this class is allowed. The constructor is called only once.
        """
        self.current_config = {
            # All distances should be integer values in cm.
            Configuration.Boundary_Distance: 16,  # Minimal distance between the boundary and the table configuration.
                                                  # 16 = A2NTS rotation radius / 2.
            Configuration.Min_Node_Distance: 32,  # Minimal distance between two nodes.
                                                  # 32 = A2NTS rotation radius.
            Configuration.Min_Node_Edge_Distance: 24,  # Minimal distance between a node and an edge.
                                                       # 24 = A2NTS rotation radius + A2NTS width / 2.
            Configuration.Trajectory_Node_Distance: 16,  # Distance between station boundary and station trajectory node.
                                                         # Distance has no physical meaning. Must be equal or larger than Boundary_Distance.
            Configuration.Buffer_Node_Distance: 32,  # Minimal distance between a buffer node and a station node.
            Configuration.Dim_Table_X: 100,  # Dimension of the tables in x direction (when angle is 0 degrees).
            Configuration.Dim_Table_Y: 50,  # Dimension of the tables in y direction (when angle is 0 degrees).
            Configuration.Dim_X: dim_x,  # Dimension of the usable area in x direction. Depends on the production layout.
            Configuration.Dim_Y: dim_y,  # Dimension of the usable area in y direction. Depends on the production layout.
            Configuration.Blocked_Space_Value: 0.55  # Value is used or the visualization.
        }

    def get(self, entry):
        return self.current_config[entry]

    def set(self, entry, value):
        if entry in self.current_config.keys():
            self.current_config[entry] = value
        else:
            raise ValueError(f"Invalid entry: {entry}")