import prodsys
from prodsys.models import production_system_data, resource_data, sink_data, source_data, node_data, port_data
from prodsys.models.production_system_data import get_production_resources
from prodsys.models.layout_data import LayoutAreaData, ObstacleData
from prodsys.util.node_link_generation.table_configuration import TableConfiguration
from prodsys.util.node_link_generation.table_configuration import StationConfiguration
from prodsys.util.node_link_generation.table_configuration import Visualization
from prodsys.util.node_link_generation.table_configuration_nodes_edges import NodeEdgeGenerator
from prodsys.util.node_link_generation.edge_directionality import EdgeDirectionality 
from prodsys.util.node_link_generation.configuration import Configuration 
import networkx as nx
import prodsys.util.node_link_generation.format_to_networkx as format_to_networkx
from typing import List, Any, Set, Optional, Tuple, Union


# ---------------------------------------------------------------------------
# Internal helpers: convert prodsys model objects → internal station/table dicts
# ---------------------------------------------------------------------------

def _layout_area_to_table(area: LayoutAreaData) -> dict:
    """Convert a ``LayoutAreaData`` into the internal table-corner-dict format."""
    return {
        "corner_nodes": [
            {"pose": [area.x_min, area.y_min, 0]},
            {"pose": [area.x_max, area.y_min, 0]},
            {"pose": [area.x_max, area.y_max, 0]},
            {"pose": [area.x_min, area.y_max, 0]},
        ],
        "center_node": [
            {"pose": [
                (area.x_min + area.x_max) / 2,
                (area.y_min + area.y_max) / 2,
                0,
            ]}
        ],
    }


def _resource_to_station_item(resource) -> dict:
    """
    Build the ``generate_stations_config`` input item for a resource.

    Resources are always treated as **zero-size point stations** for routing
    purposes so that their trajectory node lands exactly on their declared
    ``location`` and the NX→prodsys ID mapping in ``convert_nx_to_prodsys``
    works correctly.

    The ``ResourceFootprint`` field is intentionally kept as *visual-only*
    metadata: ``plot_layout`` reads it to draw scaled bounding boxes, but it
    does not affect path planning.  Physical blocking is modelled through
    ``ObstacleData`` entries in ``LayoutData``.
    """
    x, y = resource.location[0], resource.location[1]
    return [x, y, 0, 0.0, 0.0, "U"]


def _obstacle_to_station_item(obstacle: ObstacleData) -> dict:
    """Build a station item for an obstacle (no trajectory nodes)."""
    x, y = obstacle.location[0], obstacle.location[1]
    return [x, y, 0, obstacle.width, obstacle.height, "O"]


def generate_stations_config(stations: list) -> dict:
    """
    Convert a list of station items into the physical-objects dict expected by
    ``StationConfiguration.add_stations``.

    Each station item is a list with the form::

        [x, y, z, width, height, type]

    where *type* is one of:

    - ``"U"`` – unidirectional (one trajectory node on the positive-x side).
    - ``"B"`` – bidirectional (two trajectory nodes on opposite sides).
    - ``"O"`` – obstacle only (no trajectory nodes).

    For ``"U"`` and ``"B"``, *width* is used as the half-distance to the
    bounding-box edge, and the trajectory node is placed a further
    ``Trajectory_Node_Distance`` beyond that edge so it always falls clearly
    outside the station's blocked area and passes the cfree check.
    Zero-footprint (point) stations keep their trajectory at the centre.
    """
    new_data = {"physical_objects": []}
    # Zero offset: point-station trajectories land exactly at the declared
    # location so the NX→prodsys mapping in convert_nx_to_prodsys works.
    Trajectory_Node_Distance = 0

    for station in stations:
        x, y, z = station[0], station[1], station[2]
        width, height = station[3], station[4]
        stype = station[5]

        half_w = width / 2.0
        half_h = height / 2.0

        bounding_box = [
            [-half_w, -half_h, 0],
            [half_w, half_h, 0],
        ]

        if stype == "O":
            # Pure obstacle – no trajectory nodes, just occupies space.
            station_data = {
                "base": "obstacle",
                "pose": [x, y, z],
                "bounding_box": bounding_box,
                "poi": {},
            }
        elif stype == "U":
            traj_x = half_w + Trajectory_Node_Distance
            station_data = {
                "base": "if2",
                "pose": [x, y, z],
                "bounding_box": bounding_box,
                "poi": {
                    "in_port.trajectory_node": [traj_x, 0, 0],
                    "out_port.trajectory_node": [traj_x, 0, 0],
                },
            }
        elif stype == "B":
            traj_x = half_w + Trajectory_Node_Distance
            station_data = {
                "base": "if2",
                "pose": [x, y, z],
                "bounding_box": bounding_box,
                "poi": {
                    "in_port.trajectory_node": [traj_x, 0, 0],
                    "out_port.trajectory_node": [-traj_x, 0, 0],
                },
            }
        else:
            raise ValueError(f"Unknown station type: {stype!r}")

        new_data["physical_objects"].append(station_data)

    return new_data


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def get_all_locations(productionsystem: production_system_data.ProductionSystemData):
    locations = []
    for node in (
        list(productionsystem.resource_data)
        + list(productionsystem.source_data)
        + list(productionsystem.sink_data)
    ):
        locations.append([node.ID, [x for x in node.location]])
    return locations


def find_borders(productionsystem: production_system_data.ProductionSystemData):
    """Find the axis-aligned bounding box of all resource/source/sink locations."""
    stations = get_all_locations(productionsystem)
    max_x, max_y = stations[0][1]
    min_x, min_y = stations[0][1]
    for station in stations:
        if station[1][0] > max_x:
            max_x = station[1][0]
        if station[1][1] > max_y:
            max_y = station[1][1]
        if station[1][0] < min_x:
            min_x = station[1][0]
        if station[1][1] < min_y:
            min_y = station[1][1]
    return min_x, min_y, max_x, max_y


def _extract_areas_from_model(
    productionsystem: production_system_data.ProductionSystemData,
) -> Optional[list]:
    """
    Return the internal table list from ``ProductionSystemData.layout_data.areas``,
    or ``None`` if no areas are defined (falls back to auto-border detection).
    """
    if productionsystem.layout_data and productionsystem.layout_data.areas:
        return [_layout_area_to_table(area) for area in productionsystem.layout_data.areas]
    return None


def _build_all_station_items(
    productionsystem: production_system_data.ProductionSystemData,
) -> list:
    """
    Collect station items for every resource/source/sink AND every obstacle.

    Resources, sources, and sinks use **zero-size point stations** (trajectory
    at a single point, no bounding-box) so the cfree polygon has no machine
    holes and the outer-boundary walker does not deposit corner nodes at machine
    edges.

    For footprinted resources whose port has been **relocated to the footprint
    boundary** (via :func:`relocate_ports_to_footprint_boundary`), the station
    is placed at the *port position* rather than the machine centre.  This puts
    the trajectory node directly on the footprint boundary so the Delaunay
    triangulation has a proper entry point for that machine without any edge
    crossing the machine body.

    Obstacles from ``layout_data`` are given their declared dimensions so they
    properly block free-space paths.
    """
    port_lookup = {p.ID: p for p in productionsystem.port_data}
    items = []

    for resource in productionsystem.resource_data:
        # For footprinted resources whose port has been relocated to the
        # boundary, place the station AT the port so the trajectory node
        # lands at the access point rather than the (interior) machine centre.
        if resource.footprint is not None and resource.ports:
            port = port_lookup.get(resource.ports[0])
            if port is not None and port.location is not None:
                ploc = port.location
                cloc = resource.location
                if abs(ploc[0] - cloc[0]) > 0.01 or abs(ploc[1] - cloc[1]) > 0.01:
                    items.append([ploc[0], ploc[1], 0, 0.0, 0.0, "U"])
                    continue
        items.append([resource.location[0], resource.location[1], 0, 0.0, 0.0, "U"])

    for node in list(productionsystem.source_data) + list(productionsystem.sink_data):
        items.append([node.location[0], node.location[1], 0, 0.0, 0.0, "U"])

    if productionsystem.layout_data:
        for obstacle in productionsystem.layout_data.obstacles:
            items.append(_obstacle_to_station_item(obstacle))

    return items


# ---------------------------------------------------------------------------
# Graph generator
# ---------------------------------------------------------------------------

def generator(
    productionsystem: production_system_data.ProductionSystemData,
    area=None,
    visualize=False,
    style="grid",
    simple_connection=True,
) -> nx.Graph:
    """
    Generate a traversability graph for the production system.

    Layout areas are resolved in the following priority order:

    1. ``area`` argument (explicit override, e.g. from a legacy XML parse).
    2. ``productionsystem.layout_data.areas`` (model-driven layout).
    3. Auto-derived bounding box from resource/source/sink locations.

    Obstacles from ``productionsystem.layout_data.obstacles`` are always
    injected as blocking stations regardless of which area source is used.
    """
    all_station_items = _build_all_station_items(productionsystem)
    stations = generate_stations_config(all_station_items)

    # --- Determine table area ---
    if area is not None:
        tables = area
        min_x, min_y, _ = tables[0]["corner_nodes"][0]["pose"]
        max_x, max_y, _ = tables[0]["corner_nodes"][0]["pose"]
        for table in tables:
            for corner in table["corner_nodes"]:
                if corner["pose"][0] > max_x:
                    max_x = corner["pose"][0]
                if corner["pose"][1] > max_y:
                    max_y = corner["pose"][1]
                if corner["pose"][0] < min_x:
                    min_x = corner["pose"][0]
                if corner["pose"][1] < min_y:
                    min_y = corner["pose"][1]
        dim_x, dim_y = max_x - min_x, max_y - min_y

    else:
        model_areas = _extract_areas_from_model(productionsystem)

        if model_areas is not None:
            tables = model_areas
            min_x = min(t["corner_nodes"][0]["pose"][0] for t in tables)
            min_y = min(t["corner_nodes"][0]["pose"][1] for t in tables)
            max_x = max(t["corner_nodes"][2]["pose"][0] for t in tables)
            max_y = max(t["corner_nodes"][2]["pose"][1] for t in tables)
            dim_x, dim_y = max_x - min_x, max_y - min_y

        else:
            # Auto-derive from resource locations
            min_x, min_y, max_x, max_y = find_borders(productionsystem)
            range_x = max_x - min_x
            range_y = max_y - min_y
            margin_x = max(min(range_x * 0.1, 10.0), 1.0)
            margin_y = max(min(range_y * 0.1, 10.0), 1.0)
            tableXMin = min_x - margin_x
            tableYMin = min_y - margin_y
            tableXMax = max_x + margin_x
            tableYMax = max_y + margin_y
            tables = {
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
                ],
            }
            dim_x = tableXMax - tableXMin
            dim_y = tableYMax - tableYMin

    # --- Configuration ---
    config = Configuration()
    config.set(Configuration.Dim_X, int(dim_x))
    config.set(Configuration.Dim_Y, int(dim_y))

    tablesize = min(dim_x, dim_y)

    # Compute the actual grid spacing first so we can sync it with the
    # Configuration clearance values.  The original Configuration was designed
    # for centimetre-scale layouts (dim ~100–1000 cm); when coordinates are in
    # metres the raw scale-factor reduction produces a clearance that is far
    # larger than the grid spacing, causing almost every candidate node to fail
    # the distance check.
    if not simple_connection:
        min_node_distance = max(0.1 * tablesize, 10)
        max_node_distance = 0.2 * tablesize
    else:
        if tablesize < 10.0:
            min_node_distance = max(tablesize / 5.0, 0.3)
            max_node_distance = max(tablesize / 4.0, 0.5)
        else:
            min_node_distance = max(0.1 * tablesize, 0.5)
            max_node_distance = max(0.15 * tablesize, 1.0)

    original_min_node_dist = config.get(Configuration.Min_Node_Distance)
    original_min_edge_dist = config.get(Configuration.Min_Node_Edge_Distance)
    original_trajectory_dist = config.get(Configuration.Trajectory_Node_Distance)
    original_buffer_dist = config.get(Configuration.Buffer_Node_Distance)

    if tablesize < 50.0:
        scale_factor = max(tablesize / 50.0, 0.1)
        # Use the computed grid spacing as Min_Node_Distance so that the
        # internal clearance checks in get_station_nodes_in_cfree and
        # define_global_grid are consistent with the grid we will generate.
        # The scale-factor formula (32 * scale_factor) produces values that
        # are orders of magnitude too large for metre-scale layouts.
        config.set(Configuration.Min_Node_Distance, max(int(min_node_distance), 1))
        # For small layouts the grid spacing is often < 2 units, so integer
        # rounding cannot represent the sub-unit edge-clearance needed to let
        # Delaunay connect neighbouring grid nodes.  Setting it to 0 disables
        # the node-proximity veto for edges; the footprint post-processing
        # step still removes any edge that crosses a machine body.
        scaled_edge_dist = int(original_min_edge_dist * scale_factor)
        # If the scaled edge-clearance equals or exceeds the node spacing, every
        # candidate Delaunay edge would be vetoed.  Use 0 in that case so edges
        # are judged only by the footprint post-processing step.
        config.set(Configuration.Min_Node_Edge_Distance, 0 if scaled_edge_dist >= int(min_node_distance) else scaled_edge_dist)
        config.set(Configuration.Trajectory_Node_Distance, max(int(original_trajectory_dist * scale_factor), 1))
        config.set(Configuration.Buffer_Node_Distance, max(int(original_buffer_dist * scale_factor), 1))

    table_config = TableConfiguration(config)
    station_config = StationConfiguration(config, table_config)
    node_edge_generator = NodeEdgeGenerator(config, table_config, station_config)
    edge_directionality = EdgeDirectionality(table_config, node_edge_generator)
    visualization = Visualization(config, table_config, station_config, node_edge_generator)
    networkx_formater = format_to_networkx.NetworkXGraphGenerator(node_edge_generator.graph, station_config)

    if isinstance(tables, list):
        for table in tables:
            table_config.add_table(table["corner_nodes"], visualization)
    else:
        table_config.add_table(tables["corner_nodes"], visualization)
    table_config.generate_table_configuration()

    station_config.add_stations(stations, visualization)
    table_config.table_configuration_with_stations(station_config)

    if not simple_connection:
        table_config.define_medial_axis()

    if not simple_connection:
        table_config.define_zones()

    add_edges = False
    node_edge_generator.add_station_nodes_and_edges(add_edges=add_edges, buffer_nodes=False)

    add_nodes_between = True

    has_movable_resources = any(
        resource.can_move
        for resource in productionsystem.resource_data
        if isinstance(resource.control_policy, resource_data.TransportControlPolicy)
    )
    from prodsys.models import processes_data
    has_link_transport = any(
        isinstance(process, processes_data.LinkTransportProcessData)
        for process in productionsystem.process_data
    )

    if has_movable_resources or has_link_transport:
        node_edge_generator.add_outer_nodes_and_edges(
            edge_directionality,
            add_nodes_between=add_nodes_between,
            max_node_distance=max_node_distance,
            min_node_distance=min_node_distance,
            add_edges=add_edges,
        )

    if style == "grid":
        node_edge_generator.define_global_grid(grid_spacing=min_node_distance, adjust_spacing=False, add_corner_nodes_first=False)
    elif style == "random":
        node_edge_generator.define_random_nodes(min_node_distance=min_node_distance)

    num_nodes = len(node_edge_generator.graph.nodes)
    smaller_spacing = min_node_distance
    if num_nodes < 4:
        for attempt in range(3):
            smaller_spacing = min_node_distance / (2 ** (attempt + 1))
            smaller_spacing = max(smaller_spacing, 0.1)
            if style == "grid":
                node_edge_generator.define_global_grid(grid_spacing=smaller_spacing, adjust_spacing=False, add_corner_nodes_first=False)
            elif style == "random":
                node_edge_generator.define_random_nodes(min_node_distance=smaller_spacing)
            num_nodes = len(node_edge_generator.graph.nodes)
            if num_nodes >= 4:
                break

    if num_nodes < 4:
        very_small_spacing = 0.2
        if style == "grid":
            node_edge_generator.define_global_grid(grid_spacing=very_small_spacing, adjust_spacing=True, add_corner_nodes_first=True)
        elif style == "random":
            node_edge_generator.define_random_nodes(min_node_distance=very_small_spacing)
        num_nodes = len(node_edge_generator.graph.nodes)

    if num_nodes < 4:
        raise ValueError(
            f"Not enough nodes generated ({num_nodes}) for Delaunay triangulation (need at least 4). "
            f"Table size: {tablesize:.2f}, initial spacing: {min_node_distance:.2f}, final spacing tried: {smaller_spacing:.2f}. "
            f"Consider enlarging the layout area or using a different style."
        )

    node_edge_generator.delaunay_triangulation(nodes=node_edge_generator.graph.nodes, without_distance_check=False)

    edge_directionality.define_boundary_nodes_and_edges()

    exterior_direction = "ccw"
    edge_directionality.define_boundary_edges_directionality(exterior_direction=exterior_direction, narrow_sections_unidirectional=False)
    node_edge_generator.graph.update_graph_connections()
    if visualize:
        visualization.show_table_configuration(table_configuration=False, stations=True, station_nodes=False, nodes=True, edges=True)

    G, DiG = networkx_formater.generate_nx_graph(plot=False)

    # Restore singleton Configuration values to avoid test pollution
    if tablesize < 50.0:
        config.set(Configuration.Min_Node_Distance, original_min_node_dist)
        config.set(Configuration.Min_Node_Edge_Distance, original_min_edge_dist)
        config.set(Configuration.Trajectory_Node_Distance, original_trajectory_dist)
        config.set(Configuration.Buffer_Node_Distance, original_buffer_dist)

    # Remove any grid nodes that fall strictly inside a resource footprint.
    # Because resources use zero-size station bboxes, the cfree polygon has no
    # machine holes, so the grid may place nodes inside footprint areas.
    # Removing these nodes prevents edges from cutting through machine boxes.
    nodes_inside_footprint = []
    for node_id in list(G.nodes):
        pos = G.nodes[node_id].get("pos")
        if pos is None:
            continue
        for res in productionsystem.resource_data:
            if res.footprint is None:
                continue
            cx, cy = res.location[0], res.location[1]
            hw = res.footprint.width / 2.0
            hh = res.footprint.height / 2.0
            if (cx - hw) < pos[0] < (cx + hw) and (cy - hh) < pos[1] < (cy + hh):
                nodes_inside_footprint.append(node_id)
                break
    G.remove_nodes_from(nodes_inside_footprint)

    # Remove any Delaunay edges whose straight-line segment crosses through the
    # interior of a resource footprint.  Even with internal nodes removed, some
    # outside-to-outside connections can still cut diagonally through a machine.
    #
    # Exception: a link whose endpoint sits exactly on the footprint boundary
    # (i.e. it is the machine's own relocated port) is allowed to exit through
    # the machine body – that crossing is by construction, not a routing error.
    import shapely.geometry as _sg

    # Build a lookup: graph-node position → set of resource IDs whose port
    # sits at that position.  Used to allow "own-footprint" exits.
    _port_lookup_fp = {p.ID: p for p in productionsystem.port_data}
    _pos_to_res_id: dict = {}
    for _r in productionsystem.resource_data:
        for _pid in (_r.ports or []):
            _p = _port_lookup_fp.get(_pid)
            if _p is not None and _p.location is not None:
                _pk = tuple(_p.location)
                _pos_to_res_id.setdefault(_pk, set()).add(_r.ID)

    footprint_polys_gen: list = []
    footprint_res_ids: list = []
    for _res in productionsystem.resource_data:
        if _res.footprint is not None:
            _cx, _cy = _res.location[0], _res.location[1]
            _hw = _res.footprint.width / 2.0
            _hh = _res.footprint.height / 2.0
            footprint_polys_gen.append(
                _sg.box(_cx - _hw, _cy - _hh, _cx + _hw, _cy + _hh)
            )
            footprint_res_ids.append(_res.ID)

    if footprint_polys_gen:
        edges_crossing_footprint = []
        for u, v in list(G.edges()):
            pos_u = G.nodes[u].get("pos")
            pos_v = G.nodes[v].get("pos")
            if pos_u is None or pos_v is None:
                continue
            key_u = tuple(pos_u)
            key_v = tuple(pos_v)
            seg = _sg.LineString([pos_u, pos_v])
            for _res_id, _fp in zip(footprint_res_ids, footprint_polys_gen):
                if seg.crosses(_fp):
                    # Allow the crossing if one endpoint is this machine's own
                    # port (port relocated to the footprint boundary exits
                    # through the machine body by construction).
                    own_u = _res_id in _pos_to_res_id.get(key_u, set())
                    own_v = _res_id in _pos_to_res_id.get(key_v, set())
                    if own_u or own_v:
                        continue
                    edges_crossing_footprint.append((u, v))
                    break
        G.remove_edges_from(edges_crossing_footprint)

    return G


# ---------------------------------------------------------------------------
# Prodsys graph conversion
# ---------------------------------------------------------------------------

def convert_nx_to_prodsys(adapter: production_system_data.ProductionSystemData, G: nx.Graph):

    from prodsys.models.production_system_data import get_transport_resources
    all_locations = [(prodres.ID, prodres.location) for prodres in get_production_resources(adapter)]
    all_locations.extend([(tres.ID, tres.location) for tres in get_transport_resources(adapter)])
    all_locations.extend([(sink.ID, sink.location) for sink in adapter.sink_data])
    all_locations.extend([(source.ID, source.location) for source in adapter.source_data])

    location_to_resources: dict = {}
    for resource_id, location in all_locations:
        key = tuple(location)
        location_to_resources.setdefault(key, []).append(resource_id)

    # For footprinted resources whose port has been relocated to the boundary,
    # also register the PORT position so the station trajectory node placed
    # there (by _build_all_station_items) is mapped back to the resource.
    _port_lookup_conv = {p.ID: p for p in adapter.port_data}
    for res in adapter.resource_data:
        if res.footprint is None or not res.ports:
            continue
        port = _port_lookup_conv.get(res.ports[0])
        if port is None or port.location is None:
            continue
        ploc = port.location
        cloc = res.location
        if abs(ploc[0] - cloc[0]) > 0.01 or abs(ploc[1] - cloc[1]) > 0.01:
            port_key = tuple(ploc)
            if res.ID not in location_to_resources.get(port_key, []):
                location_to_resources.setdefault(port_key, []).append(res.ID)

    nx_to_location = {}
    node_id_to_name = {}
    new_nodes = []
    node_blocks = G.nodes
    for block in node_blocks:
        pos = G.nodes[block].get("pos")
        if len(pos) >= 2:
            x = pos[0]
            y = pos[1]
        else:
            raise ValueError(f"Node {block} position is not two-dimensional: {pos}")

        nx_to_location[block] = pos
        node_name = f"node_{block}"
        if pos not in location_to_resources:
            new_nodes.append([node_name, (x, y)])
            node_id_to_name[block] = node_name
        else:
            node_id_to_name[block] = None

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
            if tgt_loc in location_to_resources:
                pass
            else:
                tgt_name = node_id_to_name.get(tgt_id)
                if tgt_name:
                    for src_resource in location_to_resources[src_loc]:
                        new_links.append([src_resource, tgt_name])
                if not tgt_name and tgt_loc in location_to_resources:
                    for src_resource in location_to_resources[src_loc]:
                        for tgt_resource in location_to_resources[tgt_loc]:
                            new_links.append([src_resource, tgt_resource])
        elif tgt_loc in location_to_resources:
            src_name = node_id_to_name.get(src_id)
            if src_name:
                for tgt_resource in location_to_resources[tgt_loc]:
                    new_links.append([src_name, tgt_resource])
            if not src_name and src_loc in location_to_resources:
                for src_resource in location_to_resources[src_loc]:
                    for tgt_resource in location_to_resources[tgt_loc]:
                        new_links.append([src_resource, tgt_resource])
        else:
            src_name = node_id_to_name.get(src_id)
            tgt_name = node_id_to_name.get(tgt_id)

            if src_name and tgt_name:
                new_links.append([src_name, tgt_name])
            elif src_name and not tgt_name:
                if tgt_loc in location_to_resources:
                    for tgt_resource in location_to_resources[tgt_loc]:
                        new_links.append([src_name, tgt_resource])
            elif not src_name and tgt_name:
                if src_loc in location_to_resources:
                    for src_resource in location_to_resources[src_loc]:
                        new_links.append([src_resource, tgt_name])
            elif not src_name and not tgt_name:
                if src_loc in location_to_resources and tgt_loc in location_to_resources:
                    for src_resource in location_to_resources[src_loc]:
                        for tgt_resource in location_to_resources[tgt_loc]:
                            new_links.append([src_resource, tgt_resource])

    # Ensure all resources/sources/sinks are connected
    connected_resources = set()
    for link in new_links:
        connected_resources.add(link[0])
        connected_resources.add(link[1])

    all_resource_ids = {r[0] for r in all_locations}
    unconnected_resources = {rid for rid in all_resource_ids if rid not in connected_resources}

    # Collect IDs that actually have simulation ports.  Transport resources
    # (AGVs, conveyors) have no ports; linking to them in the fallback
    # produces no usable simulation edges, so they are excluded.
    resources_with_ports: set = set()
    for res in adapter.resource_data:
        if res.ports:
            resources_with_ports.add(res.ID)
    for src in adapter.source_data:
        if src.ports:
            resources_with_ports.add(src.ID)
    for snk in adapter.sink_data:
        if snk.ports:
            resources_with_ports.add(snk.ID)

    if unconnected_resources and nx_to_location:
        def find_nearest_node_id(resource_loc):
            min_dist = float("inf")
            nearest_id = None
            for node_id, node_loc in nx_to_location.items():
                if len(node_loc) >= 2 and len(resource_loc) >= 2:
                    dx = node_loc[0] - resource_loc[0]
                    dy = node_loc[1] - resource_loc[1]
                    dist = (dx * dx + dy * dy) ** 0.5
                    if dist < min_dist:
                        min_dist = dist
                        nearest_id = node_id
            return nearest_id

        for resource_id in unconnected_resources:
            resource_loc = next((r[1] for r in all_locations if r[0] == resource_id), None)
            if resource_loc:
                # Only consider resources that have ports as fallback targets,
                # so the resulting link produces valid simulation edges.
                nearest_connected_resource = None
                min_dist_to_resource = float("inf")
                for link in new_links:
                    for target in [link[0], link[1]]:
                        if (
                            target in all_resource_ids
                            and target in connected_resources
                            and target in resources_with_ports
                        ):
                            target_loc = next((r[1] for r in all_locations if r[0] == target), None)
                            if target_loc and len(target_loc) >= 2 and len(resource_loc) >= 2:
                                dx = target_loc[0] - resource_loc[0]
                                dy = target_loc[1] - resource_loc[1]
                                dist = (dx * dx + dy * dy) ** 0.5
                                if dist < min_dist_to_resource:
                                    min_dist_to_resource = dist
                                    nearest_connected_resource = target

                if nearest_connected_resource:
                    new_links.append([resource_id, nearest_connected_resource])
                    new_links.append([nearest_connected_resource, resource_id])
                else:
                    nearest_node_id = find_nearest_node_id(resource_loc)
                    if nearest_node_id is not None:
                        nearest_node_name = node_id_to_name.get(nearest_node_id)
                        if nearest_node_name:
                            new_links.append([resource_id, nearest_node_name])
                            new_links.append([nearest_node_name, resource_id])
                        else:
                            nearest_node_loc = nx_to_location.get(nearest_node_id)
                            if nearest_node_loc and tuple(nearest_node_loc) in location_to_resources:
                                nearest_resource = location_to_resources[tuple(nearest_node_loc)][0]
                                if nearest_resource in connected_resources:
                                    new_links.append([resource_id, nearest_resource])
                                    new_links.append([nearest_resource, resource_id])

    # Replace resource/source/sink IDs with their port IDs so the link graph
    # references ports directly.  This makes the stored links explicit and lets
    # the route-finder navigate to the correct physical locations (port positions
    # that may have been relocated to the footprint boundary).
    # Transport resources that have no ports keep their resource ID.
    id_to_port_ids: dict = {}
    for res in adapter.resource_data:
        if res.ports:
            id_to_port_ids[res.ID] = res.ports
    for src in adapter.source_data:
        if src.ports:
            id_to_port_ids[src.ID] = src.ports
    for snk in adapter.sink_data:
        if snk.ports:
            id_to_port_ids[snk.ID] = snk.ports

    expanded_links: list = []
    seen: set = set()
    for src, tgt in new_links:
        for si in id_to_port_ids.get(src, [src]):
            for ti in id_to_port_ids.get(tgt, [tgt]):
                key = (si, ti)
                if key not in seen:
                    seen.add(key)
                    expanded_links.append([si, ti])

    return new_nodes, expanded_links


def apply_nodes_links(adapter: production_system_data.ProductionSystemData, nodes, links) -> None:
    adapter.node_data = []
    for node in nodes:
        adapter.node_data.append(node_data.NodeData(ID=str(node[0]), description="", location=node[1]))

    for LinkTransportProcess in adapter.process_data:
        if isinstance(LinkTransportProcess, prodsys.processes_data.LinkTransportProcessData):
            LinkTransportProcess.links = links


def generate_and_apply_network(
    adapter: production_system_data.ProductionSystemData,
    xml_path: Optional[str] = None,
    visualize: bool = False,
    style: str = "grid",
    simple_connection: bool = True,
) -> None:
    """
    Generate a traversability graph and apply the resulting nodes and links to the adapter.

    Layout areas are resolved in priority order:

    1. ``adapter.layout_data.areas`` – areas defined directly in the prodsys model.
    2. ``xml_path`` – legacy draw.io XML file (kept for backwards compatibility).
    3. Auto-derived bounding box from resource/source/sink positions.

    Obstacles defined in ``adapter.layout_data.obstacles`` are always respected,
    regardless of which area source is used.

    Args:
        adapter: The production system to update in-place.
        xml_path: Optional path to a draw.io XML file.  Ignored when the adapter
            already has ``layout_data.areas`` defined.
        visualize: Show a matplotlib plot of the generated graph.
        style: Node-generation style – ``"grid"`` or ``"random"``.
        simple_connection: Use the simplified (faster) connection algorithm.
    """
    tables = None

    # Model-defined areas take precedence over the XML file
    if adapter.layout_data and adapter.layout_data.areas:
        tables = None  # generator() will read from model directly
    elif xml_path:
        tables = _parse_drawio_rectangles(xml_path)

    G = generator(adapter, area=tables, visualize=visualize, style=style, simple_connection=simple_connection)
    nodes, links = convert_nx_to_prodsys(adapter, G)
    apply_nodes_links(adapter, nodes, links)


def get_new_links(
    adapter: production_system_data.ProductionSystemData,
    style: str = "grid",
    simple_connection: bool = True,
) -> List[Tuple[str, str]]:
    G = generator(adapter, style=style, simple_connection=simple_connection)
    _, new_links = convert_nx_to_prodsys(adapter, G)
    return new_links


# ---------------------------------------------------------------------------
# Legacy XML support (kept for backwards compatibility)
# ---------------------------------------------------------------------------

def _parse_drawio_rectangles(xml_path: str) -> list:
    """
    Parse a draw.io XML file and return a list of table-corner dicts.

    .. deprecated::
        Prefer defining layout areas directly via ``ProductionSystemData.layout_data``
        using :class:`~prodsys.models.layout_data.LayoutData` and
        :class:`~prodsys.models.layout_data.LayoutAreaData`.
    """
    import xml.etree.ElementTree as ET

    tree = ET.parse(xml_path)
    root = tree.getroot()
    tables = []

    for cell in root.iter("mxCell"):
        if cell.get("vertex") != "1":
            continue

        style = cell.get("style", "")
        rotation = None
        for part in style.split(";"):
            if part.startswith("rotation="):
                rotation = float(part.split("=")[1])
        if rotation not in (None, 0):
            raise ValueError(f"Non-right-angle rotation detected in cell {cell.get('id')}.")

        geom = cell.find("mxGeometry")
        if geom is None:
            continue

        x = float(geom.get("x", 0))
        y = float(geom.get("y", 0))
        w = float(geom.get("width", 0))
        h = float(geom.get("height", 0))

        tables.append({
            "corner_nodes": [
                {"pose": [x, y, 0]},
                {"pose": [x + w, y, 0]},
                {"pose": [x + w, y + h, 0]},
                {"pose": [x, y + h, 0]},
            ],
            "center_node": [
                {"pose": [(x + x + w) / 2, (y + y + h) / 2, 0]}
            ],
        })

    return tables


# Keep the old public name as an alias so existing call-sites don't break.
parse_drawio_rectangles = _parse_drawio_rectangles


# ---------------------------------------------------------------------------
# Port relocation
# ---------------------------------------------------------------------------

def relocate_ports_to_footprint_boundary(
    adapter: production_system_data.ProductionSystemData,
    side: str = "right",
) -> production_system_data.ProductionSystemData:
    """
    Move the ports of footprinted production resources from the resource centre
    to the specified edge of their ``ResourceFootprint`` bounding box.

    Physically, products enter and leave a machine at its boundary rather than
    at its geometric centre.  Relocating ports to the boundary makes transport-
    time calculations more accurate (AGVs navigate to the machine edge) and
    ensures ``plot_layout`` renders port markers at the correct position.

    Call this function **after** ``add_default_queues_to_production_system``
    and **before** ``generate_and_apply_network``.

    Args:
        adapter: The production system to update in-place.
        side: Which footprint edge to place the port on:

              - ``"right"``  (+x, default) – the side facing the positive-x aisle.
              - ``"left"``   (-x).
              - ``"top"``    (+y).
              - ``"bottom"`` (-y).

    Returns:
        The same adapter object (modified in-place).

    Example::

        add_default_queues_to_production_system(adapter, reset=False)
        node_link_generation.relocate_ports_to_footprint_boundary(adapter)
        node_link_generation.generate_and_apply_network(adapter)
    """
    from prodsys.models import processes_data as _proc

    transport_process_ids: set = {
        p.ID
        for p in adapter.process_data
        if isinstance(p, (_proc.TransportProcessData, _proc.LinkTransportProcessData))
    }

    port_lookup = {p.ID: p for p in adapter.port_data}

    for resource in adapter.resource_data:
        if resource.footprint is None:
            continue
        # Skip transport resources (AGVs / conveyors) – they have no production ports.
        if all(pid in transport_process_ids for pid in resource.process_ids):
            continue
        if not resource.ports:
            continue

        cx, cy = float(resource.location[0]), float(resource.location[1])
        hw = resource.footprint.width / 2.0
        hh = resource.footprint.height / 2.0

        if side == "right":
            port_loc = [cx + hw, cy]
        elif side == "left":
            port_loc = [cx - hw, cy]
        elif side == "top":
            port_loc = [cx, cy + hh]
        elif side == "bottom":
            port_loc = [cx, cy - hh]
        else:
            raise ValueError(
                f"Unknown side {side!r}. Use 'right', 'left', 'top', or 'bottom'."
            )

        for port_id in resource.ports:
            port = port_lookup.get(port_id)
            if port is not None:
                port.location = port_loc

    return adapter


# ---------------------------------------------------------------------------
# Layout validation
# ---------------------------------------------------------------------------

def validate_no_links_cross_footprints(
    ps: production_system_data.ProductionSystemData,
) -> None:
    """
    Assert that no link segment in any ``LinkTransportProcessData`` passes
    through the interior of a resource footprint bounding box.

    Physically, a transport carrier must route *around* machines, not through
    them.  A link that crosses a footprint would represent a collision path.

    Raises:
        AssertionError: Listing every violating link and the footprint it crosses.
    """
    from shapely.geometry import LineString
    from shapely.geometry import box as _shapely_box
    from prodsys.models import processes_data as _proc

    port_lookup = {p.ID: p for p in ps.port_data}
    node_lookup = {n.ID: n for n in ps.node_data}

    def _loc(id_: str):
        if id_ in port_lookup and port_lookup[id_].location:
            return tuple(port_lookup[id_].location)
        if id_ in node_lookup:
            return tuple(node_lookup[id_].location)
        for obj in (*ps.resource_data, *ps.source_data, *ps.sink_data):
            if obj.ID == id_:
                return tuple(obj.location)
        return None

    footprint_boxes = []
    for r in ps.resource_data:
        if r.footprint:
            cx, cy = r.location
            hw, hh = r.footprint.width / 2, r.footprint.height / 2
            footprint_boxes.append(
                (r.ID, _shapely_box(cx - hw, cy - hh, cx + hw, cy + hh))
            )

    # Build a lookup: location → resource IDs that own a port at that location.
    # Links from a machine's own boundary port are allowed to exit through that
    # machine's footprint (the crossing is by construction, not a routing error).
    _port_lookup_val = {p.ID: p for p in ps.port_data}
    _port_pos_to_res: dict = {}
    for _r in ps.resource_data:
        for _pid in (_r.ports or []):
            _p = _port_lookup_val.get(_pid)
            if _p is not None and _p.location is not None:
                _pk = tuple(_p.location)
                _port_pos_to_res.setdefault(_pk, set()).add(_r.ID)

    total_links = 0
    violations: list = []
    for proc in ps.process_data:
        if not isinstance(proc, _proc.LinkTransportProcessData):
            continue
        for src_id, tgt_id in proc.links:
            total_links += 1
            src_loc = _loc(src_id)
            tgt_loc = _loc(tgt_id)
            if src_loc is None or tgt_loc is None or src_loc == tgt_loc:
                continue
            seg = LineString([src_loc, tgt_loc])
            for res_id, fp_box in footprint_boxes:
                if seg.crosses(fp_box):
                    # Allow own-footprint exits from boundary ports.
                    own_src = res_id in _port_pos_to_res.get(src_loc, set())
                    own_tgt = res_id in _port_pos_to_res.get(tgt_loc, set())
                    if own_src or own_tgt:
                        continue
                    violations.append(
                        f"  [{src_id} → {tgt_id}] crosses through footprint of {res_id}"
                    )

    if violations:
        raise AssertionError(
            f"validate_no_links_cross_footprints FAILED "
            f"({len(violations)} violation(s) in {total_links} links):\n"
            + "\n".join(violations)
        )
    print(
        f"  ✓ validate_no_links_cross_footprints  "
        f"({total_links} links checked, 0 violations)"
    )


def validate_all_ports_connected(
    ps: production_system_data.ProductionSystemData,
) -> None:
    """
    Assert that every port of every production resource, source, and sink
    appears as an endpoint in at least one link of a ``LinkTransportProcessData``.

    A disconnected port means the resource is unreachable by transport, which
    will cause simulation deadlocks.

    Raises:
        AssertionError: Listing every disconnected port.
    """
    from prodsys.models import processes_data as _proc

    ids_in_links: set = set()
    for proc in ps.process_data:
        if not isinstance(proc, _proc.LinkTransportProcessData):
            continue
        for src_id, tgt_id in proc.links:
            ids_in_links.add(src_id)
            ids_in_links.add(tgt_id)

    missing: list = []
    for r in ps.resource_data:
        for port_id in (r.ports or []):
            if port_id not in ids_in_links:
                missing.append(f"  Resource {r.ID}: port {port_id} not in any link")
    for s in ps.source_data:
        for port_id in (s.ports or []):
            if port_id not in ids_in_links:
                missing.append(f"  Source {s.ID}: port {port_id} not in any link")
    for k in ps.sink_data:
        for port_id in (k.ports or []):
            if port_id not in ids_in_links:
                missing.append(f"  Sink {k.ID}: port {port_id} not in any link")

    if missing:
        raise AssertionError(
            f"validate_all_ports_connected FAILED "
            f"({len(missing)} disconnected port(s)):\n" + "\n".join(missing)
        )
    print(
        f"  ✓ validate_all_ports_connected  "
        f"({len(ids_in_links)} unique IDs reachable in link graph)"
    )


def validate_ports_on_footprint_boundary(
    ps: production_system_data.ProductionSystemData,
    tolerance: float = 0.5,
) -> None:
    """
    Assert that every port of a footprinted production resource lies on the
    boundary of the resource's footprint bounding box (within ``tolerance``).

    After :func:`relocate_ports_to_footprint_boundary` the port must be on
    one of the four edges:

    - left:   ``x ≈ cx − width/2``
    - right:  ``x ≈ cx + width/2``
    - bottom: ``y ≈ cy − height/2``
    - top:    ``y ≈ cy + height/2``

    Args:
        ps: The production system to validate.
        tolerance: Allowed deviation from the exact boundary (default 0.5 units).

    Raises:
        AssertionError: Listing every port that violates the boundary constraint.
    """
    from prodsys.models import processes_data as _proc_val

    transport_process_ids_val: set = {
        p.ID
        for p in ps.process_data
        if isinstance(p, (_proc_val.TransportProcessData, _proc_val.LinkTransportProcessData))
    }

    port_lookup = {p.ID: p for p in ps.port_data}
    violations: list = []

    for r in ps.resource_data:
        if r.footprint is None or not r.ports:
            continue
        # Skip transport resources – their ports are not relocated by
        # relocate_ports_to_footprint_boundary, so checking them here would
        # produce false positives.
        if r.process_ids and all(pid in transport_process_ids_val for pid in r.process_ids):
            continue
        cx, cy = float(r.location[0]), float(r.location[1])
        hw, hh = r.footprint.width / 2.0, r.footprint.height / 2.0
        x_min, x_max = cx - hw, cx + hw
        y_min, y_max = cy - hh, cy + hh

        for port_id in r.ports:
            port = port_lookup.get(port_id)
            if port is None or port.location is None:
                violations.append(
                    f"  Resource {r.ID}: port {port_id} has no location set"
                )
                continue
            px, py = float(port.location[0]), float(port.location[1])

            on_left   = abs(px - x_min) <= tolerance and (y_min - tolerance) <= py <= (y_max + tolerance)
            on_right  = abs(px - x_max) <= tolerance and (y_min - tolerance) <= py <= (y_max + tolerance)
            on_bottom = abs(py - y_min) <= tolerance and (x_min - tolerance) <= px <= (x_max + tolerance)
            on_top    = abs(py - y_max) <= tolerance and (x_min - tolerance) <= px <= (x_max + tolerance)

            if not (on_left or on_right or on_bottom or on_top):
                violations.append(
                    f"  Resource {r.ID}: port {port_id} at ({px:.2f}, {py:.2f}) "
                    f"is not on the boundary of footprint "
                    f"[{x_min:.1f},{y_min:.1f}]→[{x_max:.1f},{y_max:.1f}]"
                )

    if violations:
        raise AssertionError(
            f"validate_ports_on_footprint_boundary FAILED "
            f"({len(violations)} violation(s)):\n" + "\n".join(violations)
        )
    checked = sum(
        1 for r in ps.resource_data
        if r.footprint and r.ports
        and not (r.process_ids and all(pid in transport_process_ids_val for pid in r.process_ids))
    )
    print(
        f"  ✓ validate_ports_on_footprint_boundary  "
        f"({checked} production resource(s) checked, tolerance={tolerance})"
    )


# ---------------------------------------------------------------------------
# Layout visualisation
# ---------------------------------------------------------------------------

def plot_layout(
    production_system: production_system_data.ProductionSystemData,
    title: str = "Production System Layout",
    show: bool = True,
    figsize: Tuple[float, float] = (12, 8),
):
    """
    Plot the production system layout using matplotlib.

    The figure shows:

    - **Floor areas** (``layout_data.areas``) – light blue rectangles.
    - **Obstacles** (``layout_data.obstacles``) – filled dark-gray rectangles.
    - **Path nodes** (``node_data``) – small gray dots.
    - **Path edges** (links from ``LinkTransportProcess``) – thin gray lines.
    - **Production resources** – blue squares, sized by ``footprint`` when set.
    - **Transport resources** – orange circles.
    - **Sources** – green upward triangles.
    - **Sinks** – red downward triangles.

    Args:
        production_system: The production system to visualise.  Call
            ``generate_and_apply_network`` first so ``node_data`` is populated.
        title: Figure title.
        show: Call ``plt.show()`` at the end.  Set to ``False`` when embedding
            in a larger figure or saving programmatically.
        figsize: ``(width, height)`` in inches passed to ``plt.figure``.

    Returns:
        The ``matplotlib.figure.Figure`` instance.
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.lines import Line2D

    from prodsys.models.production_system_data import get_production_resources, get_transport_resources
    from prodsys.models import processes_data as processes_data_module

    fig, ax = plt.subplots(figsize=figsize)
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlabel("x")
    ax.set_ylabel("y")

    # --- floor areas --------------------------------------------------------
    if production_system.layout_data:
        for area in production_system.layout_data.areas:
            rect = mpatches.FancyBboxPatch(
                (area.x_min, area.y_min),
                area.x_max - area.x_min,
                area.y_max - area.y_min,
                boxstyle="square,pad=0",
                linewidth=1.5,
                edgecolor="#3a7ebf",
                facecolor="#ddeeff",
                alpha=0.4,
                zorder=1,
            )
            ax.add_patch(rect)
            ax.text(
                (area.x_min + area.x_max) / 2,
                area.y_max - (area.y_max - area.y_min) * 0.04,
                area.ID or area.description,
                ha="center", va="top",
                fontsize=7, color="#3a7ebf", style="italic",
                zorder=2,
            )

        # --- obstacles – drawn ABOVE path edges so lines don't show through --
        for obs in production_system.layout_data.obstacles:
            ox, oy = obs.location[0] - obs.width / 2, obs.location[1] - obs.height / 2
            rect = mpatches.FancyBboxPatch(
                (ox, oy), obs.width, obs.height,
                boxstyle="square,pad=0",
                linewidth=1,
                edgecolor="#333333",
                facecolor="#888888",
                alpha=0.9,
                zorder=7,
            )
            ax.add_patch(rect)
            ax.text(
                obs.location[0], obs.location[1],
                obs.ID,
                ha="center", va="center",
                fontsize=6, color="white", fontweight="bold",
                zorder=8,
            )

    # --- path edges ---------------------------------------------------------
    # When a resource's port has been relocated to the footprint boundary,
    # draw path edges TO the port position rather than to the machine centre.
    # This prevents the edge from visually piercing the footprint box.
    port_lookup = {p.ID: p for p in production_system.port_data}

    def _resource_edge_location(res) -> list:
        """Return the port location if it differs from the centre, else centre."""
        if res.ports:
            port = port_lookup.get(res.ports[0])
            if port and port.location:
                ploc = port.location
                cloc = res.location
                if abs(ploc[0] - cloc[0]) > 0.01 or abs(ploc[1] - cloc[1]) > 0.01:
                    return ploc
        return res.location

    all_location_objects: dict = {}
    for r in production_system.resource_data:
        all_location_objects[r.ID] = _resource_edge_location(r)
    for s in production_system.source_data:
        all_location_objects[s.ID] = s.location
    for k in production_system.sink_data:
        all_location_objects[k.ID] = k.location
    for n in production_system.node_data:
        all_location_objects[n.ID] = n.location
    # Port IDs may now appear directly in links (after the ID→port expansion).
    for p in production_system.port_data:
        if p.location is not None:
            all_location_objects[p.ID] = p.location

    for process in production_system.process_data:
        if not isinstance(process, processes_data_module.LinkTransportProcessData):
            continue
        links = process.links
        if isinstance(links, dict):
            link_pairs = [(s, t) for s, targets in links.items() for t in targets]
        else:
            link_pairs = [(s, t) for s, t in links]
        for src_id, tgt_id in link_pairs:
            src_loc = all_location_objects.get(src_id)
            tgt_loc = all_location_objects.get(tgt_id)
            if src_loc is not None and tgt_loc is not None:
                ax.plot(
                    [src_loc[0], tgt_loc[0]],
                    [src_loc[1], tgt_loc[1]],
                    color="#aaaaaa", linewidth=0.8, alpha=0.7, zorder=5,
                )

    # --- path nodes ---------------------------------------------------------
    if production_system.node_data:
        nx_vals = [n.location[0] for n in production_system.node_data]
        ny_vals = [n.location[1] for n in production_system.node_data]
        ax.scatter(nx_vals, ny_vals, s=8, color="#aaaaaa", zorder=6, label="Path nodes")

    # --- production resources + their ports ---------------------------------
    prod_resources = get_production_resources(production_system)
    port_lookup = {p.ID: p for p in production_system.port_data}
    for res in prod_resources:
        fp = res.footprint
        if fp is not None:
            rect = mpatches.FancyBboxPatch(
                (res.location[0] - fp.width / 2, res.location[1] - fp.height / 2),
                fp.width, fp.height,
                boxstyle="square,pad=0",
                linewidth=1.5,
                edgecolor="#1a56a0",
                facecolor="#4a90d9",
                alpha=1.0,
                zorder=7,
            )
            ax.add_patch(rect)
            ax.text(
                res.location[0], res.location[1],
                res.ID,
                ha="center", va="center",
                fontsize=7, color="white", fontweight="bold",
                zorder=8,
            )
        else:
            ax.scatter(
                res.location[0], res.location[1],
                s=120, marker="s", color="#4a90d9", edgecolors="#1a56a0",
                linewidths=1.5, zorder=7,
            )
            ax.text(
                res.location[0], res.location[1] + 3,
                res.ID,
                ha="center", va="bottom", fontsize=7, color="#1a56a0",
                zorder=8,
            )

        # Draw port positions when they have been relocated off-centre.
        # A dashed connector runs from the resource centre to the port so the
        # boundary access-point is visually linked to the machine body.  The
        # segment inside the machine is hidden by the blue footprint box (drawn
        # at the same zorder); only the endpoint diamond is visible above it.
        if res.ports:
            for port_id in res.ports:
                port = port_lookup.get(port_id)
                if port is None or port.location is None:
                    continue
                ploc = port.location
                cloc = res.location
                if abs(ploc[0] - cloc[0]) > 0.01 or abs(ploc[1] - cloc[1]) > 0.01:
                    # Connector: centre → port
                    ax.plot(
                        [cloc[0], ploc[0]], [cloc[1], ploc[1]],
                        color="#ffffff", linewidth=1.5, linestyle="--",
                        zorder=8,
                    )
                    # Diamond marker at the port (above the machine box)
                    ax.scatter(
                        ploc[0], ploc[1],
                        s=70, marker="D", color="#ffffff", edgecolors="#1a56a0",
                        linewidths=1.8, zorder=9,
                    )

    # --- transport resources ------------------------------------------------
    transport_resources = get_transport_resources(production_system)
    for res in transport_resources:
        ax.scatter(
            res.location[0], res.location[1],
            s=100, marker="o", color="#f5a623", edgecolors="#c07800",
            linewidths=1.5, zorder=7,
        )
        ax.text(
            res.location[0], res.location[1] + 3,
            res.ID,
            ha="center", va="bottom", fontsize=7, color="#c07800",
            zorder=8,
        )

    # --- sources ------------------------------------------------------------
    for src in production_system.source_data:
        ax.scatter(
            src.location[0], src.location[1],
            s=120, marker="^", color="#2ca02c", edgecolors="#1a6b1a",
            linewidths=1.5, zorder=7,
        )
        ax.text(
            src.location[0], src.location[1] + 3,
            src.ID,
            ha="center", va="bottom", fontsize=7, color="#1a6b1a",
            zorder=8,
        )

    # --- sinks --------------------------------------------------------------
    for snk in production_system.sink_data:
        ax.scatter(
            snk.location[0], snk.location[1],
            s=120, marker="v", color="#d62728", edgecolors="#8b0000",
            linewidths=1.5, zorder=7,
        )
        ax.text(
            snk.location[0], snk.location[1] - 3,
            snk.ID,
            ha="center", va="top", fontsize=7, color="#8b0000",
            zorder=8,
        )

    # --- legend -------------------------------------------------------------
    legend_elements = [
        mpatches.Patch(facecolor="#ddeeff", edgecolor="#3a7ebf", alpha=0.6, label="Floor area"),
        mpatches.Patch(facecolor="#888888", edgecolor="#333333", alpha=0.85, label="Obstacle"),
        Line2D([0], [0], color="#aaaaaa", linewidth=1, label="Path edge"),
        Line2D([0], [0], marker=".", color="#aaaaaa", markersize=6,
               linestyle="None", label="Path node"),
        mpatches.Patch(facecolor="#4a90d9", edgecolor="#1a56a0", label="Machine (footprint)"),
        Line2D([0], [0], marker="D", color="#ffffff", markersize=7,
               markeredgecolor="#1a56a0", markeredgewidth=1.5,
               linestyle="None", label="Machine port (boundary)"),
        Line2D([0], [0], marker="o", color="#f5a623", markersize=8,
               markeredgecolor="#c07800", linestyle="None", label="Transport resource"),
        Line2D([0], [0], marker="^", color="#2ca02c", markersize=8,
               markeredgecolor="#1a6b1a", linestyle="None", label="Source"),
        Line2D([0], [0], marker="v", color="#d62728", markersize=8,
               markeredgecolor="#8b0000", linestyle="None", label="Sink"),
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=8, framealpha=0.9)

    ax.grid(True, linestyle="--", alpha=0.3, zorder=0)
    fig.tight_layout()

    if show:
        plt.show()

    return fig
