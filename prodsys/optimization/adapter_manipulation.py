from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass
import logging
from typing import Callable, List
import networkx as nx
import pandas as pd
from prodsys import adapters
from prodsys.models.production_system_data import (
    add_default_queues_to_resources,
    get_possible_production_processes_IDs,
    get_possible_transport_processes_IDs,
    get_required_process_ids,
    remove_queues_from_resources,
    remove_unused_queues_from_adapter,
)
from prodsys.models import resource_data, scenario_data
from prodsys.models.processes_data import (
    CompoundProcessData,
    LinkTransportProcessData,
    ProcessModelData,
    TransportProcessData,
)
from prodsys.models.state_data import BreakDownStateData
from prodsys.models.time_model_data import TIME_MODEL_DATA, DistanceTimeModelData
from prodsys.optimization.optimization import check_valid_configuration
from prodsys.optimization.util import (
    add_setup_states_to_machine,
    adjust_process_capacities,
    clean_out_breakdown_states_of_resources,
    get_grouped_processes_of_machine,
    get_required_primitives,
)
from prodsys.util.node_link_generation import node_link_generation
from prodsys.models.primitives_data import StoredPrimitive
from prodsys.simulation.route_finder import find_route
from prodsys.simulation import request
import random
from uuid import uuid1

from prodsys.simulation import process, request, runner
from prodsys.util.util import flatten



from prodsys.models.primitives_data import StoredPrimitive
import random
from uuid import uuid1
from prodsys.simulation import process, request, runner
from prodsys.util.util import flatten
from prodsys.models.dependency_data import DependencyType


def _build_process_data_map(adapter_object: adapters.ProductionSystemData) -> dict[str, object]:
    """
    Create a mapping from process ID to process data object for quick lookup.
    """
    return {process.ID: process for process in adapter_object.process_data}


def _collect_leaf_process_ids(
    process_data_map: dict[str, object],
    process_id: str,
    required_ids: set[str],
    visited_models: set[str] | None = None,
) -> set[str]:
    """
    Recursively collect all non-ProcessModel process IDs contained within a ProcessModel.
    """
    if visited_models is None:
        visited_models = set()
    if process_id in visited_models:
        return set()
    process_obj = process_data_map.get(process_id)
    if not isinstance(process_obj, ProcessModelData):
        return set()
    visited_models.add(process_id)
    contained_ids: set[str] = set()
    adjacency = process_obj.adjacency_matrix or {}
    node_ids = set(adjacency.keys())
    for successors in adjacency.values():
        node_ids.update(successors)
    for node_id in node_ids:
        node_obj = process_data_map.get(node_id)
        if isinstance(node_obj, ProcessModelData):
            contained_ids.update(
                _collect_leaf_process_ids(
                    process_data_map, node_id, required_ids, visited_models
                )
            )
        elif node_obj is not None and node_id in required_ids:
            contained_ids.add(node_id)
    return contained_ids

def delete_unused_conveyor_processes(
    adapter_object: adapters.ProductionSystemData
) -> None:
    if adapters.get_conveyor_processes(adapter_object):
        unused_processes = []
        for process in adapter_object.process_data:
            unused = True
            if isinstance(process, LinkTransportProcessData):
                if not process.can_move:
                    for resource in adapter_object.resource_data:
                        if process.ID in resource.process_ids:
                            unused = False
            else: 
                unused=False
            if unused:
                unused_processes.append(process)

        for process in unused_processes:
            adapter_object.process_data.remove(process)


def sync_resource_process_ids_for_adapter(
    resource: resource_data.ResourceData,
    target_adapter: adapters.ProductionSystemData
) -> None:
    """
    Update a resource's process IDs to match processes that exist in the target adapter.
    This is needed when moving resources between adapters during crossover.
    """
    if not resource.process_ids:
        return
    
    # Get all existing process IDs in target adapter
    existing_process_ids = {p.ID for p in target_adapter.process_data}
    
    # Get transport process IDs
    transport_process_ids = set(get_possible_transport_processes_IDs(target_adapter))
    
    # Get all conveyor processes in target adapter, grouped by capability
    conveyor_processes_by_capability = {}
    all_conveyor_processes = []
    for process in target_adapter.process_data:
        if isinstance(process, LinkTransportProcessData):
            all_conveyor_processes.append(process)
            capability = process.capability or process.ID
            if capability not in conveyor_processes_by_capability:
                conveyor_processes_by_capability[capability] = process
    
    # Update resource process IDs
    updated_process_ids = []
    for proc_id in resource.process_ids:
        if proc_id in existing_process_ids:
            # Process exists in target adapter, keep it
            updated_process_ids.append(proc_id)
        elif proc_id in transport_process_ids:
            # This is a transport process that doesn't exist in target adapter
            # Find a matching conveyor process - prefer by capability, otherwise use any available
            matching_process = None
            if all_conveyor_processes:
                # Use the first available conveyor process as fallback
                # (The processes should have been copied already, so this is a fallback)
                matching_process = all_conveyor_processes[0]
            
            if matching_process:
                updated_process_ids.append(matching_process.ID)
            else:
                # No matching process found, this will cause validation error but that's better than silent failure
                updated_process_ids.append(proc_id)
        else:
            # Not a transport process, keep as is (will fail validation if it doesn't exist)
            updated_process_ids.append(proc_id)
    
    resource.process_ids = updated_process_ids


def sync_resource_conveyor_process_ids(
    adapter_object: adapters.ProductionSystemData
) -> None:
    """
    Update resource process IDs to match existing conveyor processes in the adapter.
    This is needed after network regeneration when process IDs might have changed.
    """
    # Get all existing conveyor process IDs
    existing_conveyor_process_ids = {
        p.ID for p in adapter_object.process_data 
        if isinstance(p, LinkTransportProcessData)
    }
    
    # Get conveyor processes by capability for matching
    conveyor_processes_by_capability = {}
    for process in adapter_object.process_data:
        if isinstance(process, LinkTransportProcessData):
            capability = process.capability or process.ID
            if capability not in conveyor_processes_by_capability:
                conveyor_processes_by_capability[capability] = process
    
    # Update resource process IDs to reference existing conveyor processes
    transport_process_ids = set(get_possible_transport_processes_IDs(adapter_object))
    for resource in adapter_object.resource_data:
        if any(proc_id in transport_process_ids for proc_id in (resource.process_ids or [])):
            # This is a transport resource, update its process IDs
            updated_process_ids = []
            for proc_id in resource.process_ids:
                if proc_id in transport_process_ids:
                    # Check if this process ID exists in process_data
                    if proc_id not in existing_conveyor_process_ids:
                        # Find a matching conveyor process by capability
                        # Try to find any conveyor process with matching capability
                        matching_process = None
                        for process in adapter_object.process_data:
                            if isinstance(process, LinkTransportProcessData):
                                capability = process.capability or process.ID
                                # Use the first matching process we find
                                if capability in conveyor_processes_by_capability:
                                    matching_process = conveyor_processes_by_capability[capability]
                                    break
                        
                        if matching_process:
                            updated_process_ids.append(matching_process.ID)
                        else:
                            # If no match, try to use any available conveyor process
                            if existing_conveyor_process_ids:
                                updated_process_ids.append(next(iter(existing_conveyor_process_ids)))
                            else:
                                # Keep original - will fail validation but that's better than silent failure
                                updated_process_ids.append(proc_id)
                    else:
                        updated_process_ids.append(proc_id)
                else:
                    # Not a transport process, keep as is
                    updated_process_ids.append(proc_id)
            resource.process_ids = updated_process_ids


def expand_process_ids_with_models(
    adapter_object: adapters.ProductionSystemData, process_ids: List[str]
) -> List[str]:
    """
    Ensure that process IDs derived from ProcessModels also include their nested processes.
    """
    if not process_ids:
        return []
    required_ids = set(get_required_process_ids(adapter_object))
    process_data_map = _build_process_data_map(adapter_object)
    expanded: List[str] = []
    seen: set[str] = set()
    for pid in process_ids:
        if isinstance(pid, (list, tuple, set)):
            candidate_ids = list(flatten(pid))
        else:
            candidate_ids = [pid]
        for candidate_id in candidate_ids:
            if candidate_id not in required_ids:
                continue
            if candidate_id not in seen:
                expanded.append(candidate_id)
                seen.add(candidate_id)
            leaf_ids = _collect_leaf_process_ids(
                process_data_map, candidate_id, required_ids
            )
            for leaf_id in leaf_ids:
                if leaf_id in required_ids and leaf_id not in seen:
                    expanded.append(leaf_id)
                    seen.add(leaf_id)
    return expanded


def _get_resource_dependency_ids(
    adapter_object: adapters.ProductionSystemData,
) -> set[str]:
    """
    Return the set of resource IDs referenced by resource dependencies.
    """
    if not adapter_object.dependency_data:
        return set()
    return {
        dependency.required_resource
        for dependency in adapter_object.dependency_data
        if getattr(dependency, "dependency_type", None) == DependencyType.RESOURCE
    }


def sync_resource_dependencies(adapter_object: adapters.ProductionSystemData) -> None:
    """
    Ensure that resource dependencies always reference existing resources.
    If the original resource is missing, reassign the dependency to a suitable fallback.
    """
    if not adapter_object.dependency_data:
        return

    available_resources = {resource.ID: resource for resource in adapter_object.resource_data}
    if not available_resources:
        return

    transport_resources = adapters.get_transport_resources(adapter_object)
    production_resources = adapters.get_production_resources(adapter_object)
    def _pick_fallback(description: str) -> str:
        desc = (description or "").lower()
        if "transport" in desc and transport_resources:
            return transport_resources[0].ID
        if ("production" in desc or "machine" in desc) and production_resources:
            return production_resources[0].ID
        if transport_resources:
            return transport_resources[0].ID
        if production_resources:
            return production_resources[0].ID
        # As a last resort, return any available resource ID.
        return next(iter(available_resources.keys()))

    for dependency in adapter_object.dependency_data:
        if getattr(dependency, "dependency_type", None) != DependencyType.RESOURCE:
            continue
        if dependency.required_resource in available_resources:
            continue
        fallback_id = _pick_fallback(getattr(dependency, "description", ""))
        dependency.required_resource = fallback_id

def crossover(ind1, ind2):
    ind1[0].ID = str(uuid1())
    ind2[0].ID = str(uuid1())

    crossover_type = random.choice(["machine", "partial_machine", "transport_resource"])
    adapter1: adapters.ProductionSystemData = ind1[0]
    adapter2: adapters.ProductionSystemData = ind2[0]
    machines_1 = adapters.get_production_resources(adapter1)
    machines_2 = adapters.get_production_resources(adapter2)
    # Remove queues from resources and clean up orphaned queues before swapping
    remove_queues_from_resources(machines_1 + machines_2)
    transport_resources_1 = adapters.get_transport_resources(adapter1)
    transport_resources_2 = adapters.get_transport_resources(adapter2)
    # Clean up all orphaned queues before swapping resources
    remove_unused_queues_from_adapter(adapter1)
    remove_unused_queues_from_adapter(adapter2)
    
    # Synchronize conveyor processes BEFORE swapping resources to ensure process IDs exist
    # This is needed because transport resources might reference processes from the other adapter
    # and validation happens immediately when we assign resources
    transport_processes2 = adapters.get_conveyor_processes(adapter2)
    transport_processes1 = adapters.get_conveyor_processes(adapter1)
    if (transport_processes1 or transport_processes2):
        for tp in transport_processes2:
            if not any(tp.ID == atp.ID for atp in adapter1.process_data):
                adapter1.process_data.append(tp.model_copy(deep=True))
        for tp in transport_processes1:
            if not any(tp.ID == atp.ID for atp in adapter2.process_data):
                adapter2.process_data.append(tp.model_copy(deep=True))
    
    # Sync resource process IDs to match processes in target adapter BEFORE swapping
    # This ensures resources reference process IDs that exist in the target adapter
    for resource in transport_resources_2:
        sync_resource_process_ids_for_adapter(resource, adapter1)
    for resource in transport_resources_1:
        sync_resource_process_ids_for_adapter(resource, adapter2)
    
    if "machine" in crossover_type:
        adapter1.resource_data = transport_resources_1
        adapter2.resource_data = transport_resources_2
        if crossover_type == "partial_machine":
            min_length = min(len(machines_1), len(machines_2))
            machines_1 = machines_1[:min_length] + machines_2[min_length:]
            machines_2 = machines_2[:min_length] + machines_1[min_length:]
        adapter1.resource_data += machines_2
        adapter2.resource_data += machines_1

    if crossover_type == "transport_resource":
        adapter1.resource_data = machines_1 + transport_resources_2
        adapter2.resource_data = machines_2 + transport_resources_1
        
        # Clean up unused processes after swapping
        delete_unused_conveyor_processes(adapter1)
        delete_unused_conveyor_processes(adapter2)

    # Clean up orphaned queues after swapping resources and before regenerating network
    remove_unused_queues_from_adapter(adapter1)
    remove_unused_queues_from_adapter(adapter2)

    if any(isinstance(process, LinkTransportProcessData) for process in adapter1.process_data):
        node_link_generation.generate_and_apply_network(adapter1, simple_connection=True)
        # Sync resource process IDs after network generation
        sync_resource_conveyor_process_ids(adapter1)
    if any(isinstance(process, LinkTransportProcessData) for process in adapter2.process_data):
        node_link_generation.generate_and_apply_network(adapter2, simple_connection=True)
        # Sync resource process IDs after network generation
        sync_resource_conveyor_process_ids(adapter2)
    add_default_queues_to_resources(adapter1, reset=False)
    add_default_queues_to_resources(adapter2, reset=False)
    clean_out_breakdown_states_of_resources(adapter1)
    clean_out_breakdown_states_of_resources(adapter2)
    adjust_process_capacities(adapter1)
    adjust_process_capacities(adapter2)
    sync_resource_dependencies(adapter1)
    sync_resource_dependencies(adapter2)

    return ind1, ind2


def add_machine(adapter_object: adapters.ProductionSystemData) -> bool:
    """
    Function that adds a random machine to the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if a machine was added, False otherwise (if adding is not possible due to constraint violations).
    """
    num_process_modules = (
        random.choice(
            range(
                adapter_object.scenario_data.constraints.max_num_processes_per_machine
            )
        )
        + 1
    )
    required_ids = set(get_required_process_ids(adapter_object))
    possible_processes = [
        process_module
        for process_module in get_possible_production_processes_IDs(adapter_object)
        if (
            isinstance(process_module, tuple)
            and all(process_id in required_ids for process_id in process_module)
        )
        or (isinstance(process_module, str) and process_module in required_ids)
    ]
    if num_process_modules > len(possible_processes):
        num_process_modules = len(possible_processes)
    if num_process_modules == 0 or not possible_processes:
        return False
    process_module_list = random.sample(possible_processes, num_process_modules)
    process_module_list = list(flatten(process_module_list))
    process_module_list = expand_process_ids_with_models(
        adapter_object, process_module_list
    )
    if not process_module_list:
        return False

    machine_controllers = adapter_object.scenario_data.options.machine_controllers
    if not machine_controllers:
        control_policy = "FIFO"  # Default control policy
    else:
        control_policy = random.choice(machine_controllers)
    possible_positions = deepcopy(adapter_object.scenario_data.options.positions)
    for resource in adapters.get_production_resources(adapter_object):
        if resource.location in possible_positions:
            possible_positions.remove(resource.location)
    if not possible_positions:
        return False
    machine_location = random.choice(possible_positions)
    machine_id = f"resource_{uuid1().hex}"

    adapter_object.resource_data.append(
        resource_data.ResourceData(
            ID=machine_id,
            description="",
            capacity=1,
            location=machine_location,
            controller=resource_data.ControllerEnum.PipelineController,
            control_policy=control_policy,
            process_ids=process_module_list,
        )
    )
    add_default_queues_to_resources(adapter_object, reset=False)
    add_setup_states_to_machine(adapter_object, machine_id)
    if any(isinstance(process, LinkTransportProcessData) for process in adapter_object.process_data):
        node_link_generation.generate_and_apply_network(adapter_object, simple_connection=True)
    return True


def add_transport_resource(adapter_object: adapters.ProductionSystemData) -> bool:
    """
    Function that adds a random transport resource to the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if a transport resource was added, False otherwise (if adding is not possible due to constraint violations).
    """
    transport_controllers = adapter_object.scenario_data.options.transport_controllers
    if not transport_controllers:
        control_policy = "FIFO"  # Default control policy
    else:
        control_policy = random.choice(transport_controllers)

    possible_positions = deepcopy(adapter_object.scenario_data.options.positions)
    for resource in adapters.get_production_resources(adapter_object):
        if resource.location in possible_positions:
            possible_positions.remove(resource.location)
    if not possible_positions:
        return False
    required_ids = set(get_required_process_ids(adapter_object))
    possible_processes = [
        process_id
        for process_id in get_possible_transport_processes_IDs(adapter_object)
        if process_id in required_ids or (
            process.capability in required_ids for process in adapter_object.process_data if process.ID == process_id
        )
    ]
    if not possible_processes:
        return False
    transport_process = random.choice(possible_processes)
    transport_process_data = next(process for process in adapter_object.process_data if process.ID == transport_process)
    if transport_process_data.can_move:
        transport_resource_id = f"AGV_{uuid1().hex}"
        adapter_object.resource_data.append(
            resource_data.ResourceData(
                ID=transport_resource_id,
                description="",
                capacity=1,
                location=[0,0],
                controller=resource_data.ControllerEnum.PipelineController,
                control_policy=control_policy,
                process_ids=[transport_process],
                can_move=True, 
            )
        )
    else: #case like Conveyor that cannot move: place links on a path neccessary for a random product and process
        new_links = []
        G = nx.Graph()
        if transport_process_data.capability:
            key=transport_process_data.capability
        else:
            key=transport_process
        possible_products = [product for product in adapter_object.product_data
            if product.transport_process == key]
        product = random.choice(possible_products)
        if len(product.processes) >= 2:
            idx = random.randint(0, len(product.processes) - 2)
            process_sequence = product.processes[idx:idx+2]
        else:
            process_sequence = product.processes
        for src, tgt in node_link_generation.get_new_links(adapter_object, simple_connection=True):
                G.add_edge(src, tgt)
        new_links = []
        if len(process_sequence) > 1:
            for i in range(len(process_sequence)-1): 
                if i == 0 and product.processes.index(process_sequence[i]) == 0:
                    next_process = process_sequence[0]
                    possible_current_resources = [
                        source for source in adapter_object.source_data
                        if source.product_type == product.ID
                    ]
                    possible_next_resources = [
                        resource for resource in adapter_object.resource_data
                        if next_process in resource.process_ids
                    ]
                    for next_resource in possible_next_resources:
                        for source in possible_current_resources:
                            try: #TODO: use pathfinding algorithm that considers distances
                                path = nx.shortest_path(G, source=source.ID, target=next_resource.ID)
                            except nx.NetworkXNoPath:
                                path = []  # No path found
                            for i in range(len(path)-1):
                                new_links.append((path[i], path[i+1]))
                current_process = process_sequence[i]
                next_process = process_sequence[i+1]
                possible_next_resources = [
                    resource for resource in adapter_object.resource_data
                    if next_process in resource.process_ids
                ]
                possible_current_resources = [
                    resource for resource in adapter_object.resource_data
                    if current_process in resource.process_ids
                ]
                for next_resource in possible_next_resources:
                    for source in possible_current_resources:
                        for next_resource in possible_next_resources:
                            try:
                                path = nx.shortest_path(G, source=source.ID, target=next_resource.ID)
                            except nx.NetworkXNoPath:
                                return []  # No path found
                            for i in range(len(path)-1):
                                new_links.append((path[i], path[i+1]))
                if i==len(process_sequence)-1 and product.processes.index(process_sequence[i+1]) == len(product.processes)-1:
                    possible_current_resources = possible_next_resources
                    possible_next_resources = [
                        sink for sink in adapter_object.sink_data
                        if sink.product_type == product.ID
                    ]
                    for next_resource in possible_next_resources:
                        for source in possible_current_resources:
                            try:
                                path = nx.shortest_path(G, source=source.ID, target=next_resource.ID)
                            except nx.NetworkXNoPath:
                                path = []  # No path found
                            for i in range(len(path)-1):
                                new_links.append((path[i], path[i+1]))
        else: #only one process in sequence
            possible_sources = [
                source for source in adapter_object.source_data
                if source.product_type == product.ID
            ]
            possible_resources = [
                resource for resource in adapter_object.resource_data
                if process_sequence in resource.process_ids
            ]
            possible_sinks = [
                sink for sink in adapter_object.sink_data
                if sink.product_type == product.ID
            ]
            for resource in possible_resources: #from source to resource
                for source in possible_sources:
                    try: #TODO: use pathfinding algorithm that considers distances
                        path = nx.shortest_path(G, source=source.ID, target=resource.ID)
                    except nx.NetworkXNoPath:
                        path = []  # No path found
                    for i in range(len(path)-1):
                        new_links.append((path[i], path[i+1]))
            for resource in possible_resources: #from resource to sink
                for sink in possible_sinks:
                    try:
                        path = nx.shortest_path(G, source=resource.ID, target=sink.ID)
                    except nx.NetworkXNoPath:
                        path = []  # No path found
                    for i in range(len(path)-1):
                        new_links.append((path[i], path[i+1]))
        
        new_transport_process = transport_process_data.model_copy(deep=True)
        new_transport_process.ID = f"conveyor_process_{uuid1().hex}"
        new_transport_process.links = new_links
        adapter_object.process_data.append(new_transport_process)

        possible_transport_resources = []
        for resource in adapter_object.resource_data:
            if transport_process in resource.process_ids:
                possible_transport_resources.append(resource)
        new_object_capacities = []
        try:
            for tr in possible_transport_resources:
                if tr.capacity<24:
                    new_object_capacities.append(tr.capacity)
        except IndexError:
            new_object_capacity = 1
        if new_object_capacities:
            new_object_capacity = random.choice(new_object_capacities)
        else:
            new_object_capacity = 1
        transport_resource_id = f"conveyor_{uuid1().hex}"
        new_transport_resource = resource_data.ResourceData(
                ID=transport_resource_id,
                description="",
                capacity=1,
                location=(0,0),
                controller=resource_data.ControllerEnum.PipelineController,
                control_policy=control_policy,
                process_ids=[new_transport_process.ID],
                can_move=False,
            )
        adapter_object.resource_data.append(new_transport_resource)
        if not new_transport_process.ID == adapter_object.process_data[-1].ID or not new_transport_process.ID == adapter_object.resource_data[-1].process_ids[0]:
            print("Transport process and resource are not correctly linked.") #DEBUG
    add_default_queues_to_resources(adapter_object, reset=False)
    return True


def add_process_module(adapter_object: adapters.ProductionSystemData) -> bool:
    """
    Function that adds a random process module to a random machine of the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if a process module was added, False otherwise (if adding is not possible due to constraint violations).
    """
    possible_machines = adapters.get_production_resources(adapter_object)
    if not possible_machines:
        return False
    required_ids = set(get_required_process_ids(adapter_object))
    possible_processes = [
        process_module
        for process_module in get_possible_production_processes_IDs(adapter_object)
        if (
            isinstance(process_module, tuple)
            and all(process_id in required_ids for process_id in process_module)
        )
        or (isinstance(process_module, str) and process_module in required_ids)
    ]
    machine = random.choice(possible_machines)
    if not possible_processes:
        return False
    process_module_to_add = random.sample(possible_processes, k=1)
    process_module_to_add = list(flatten(process_module_to_add))
    process_module_to_add = expand_process_ids_with_models(
        adapter_object, process_module_to_add
    )
    if not process_module_to_add:
        return False
    for process_id in process_module_to_add:
        if process_id not in machine.process_ids:
            machine.process_ids.append(process_id)
    add_setup_states_to_machine(adapter_object, machine.ID)
    return True


def remove_machine(adapter_object: adapters.ProductionSystemData) -> bool:
    """
    Function that removes a random machine from the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if a machine was removed, False otherwise (if removing is not possible due to constraint violations).
    """
    required_resource_ids = _get_resource_dependency_ids(adapter_object)
    possible_machines = [
        machine
        for machine in adapters.get_production_resources(adapter_object)
        if machine.ID not in required_resource_ids
    ]
    if not possible_machines:
        return False
    machine = random.choice(possible_machines)
    adapter_object.resource_data.remove(machine)
    return True


def remove_transport_resource(adapter_object: adapters.ProductionSystemData) -> bool:
    """
    Function that removes a random transport resource from the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if a transport resource was removed, False otherwise (if removing is not possible due to constraint violations).
    """
    required_resource_ids = _get_resource_dependency_ids(adapter_object)
    transport_resources = [
        resource
        for resource in adapters.get_transport_resources(adapter_object)
        if resource.ID not in required_resource_ids
    ]
    if not transport_resources:
        return False
    transport_resource = random.choice(transport_resources)
    adapter_object.resource_data.remove(transport_resource)
    delete_unused_conveyor_processes(adapter_object)
    if any(isinstance(process, LinkTransportProcessData) for process in adapter_object.process_data):
        node_link_generation.generate_and_apply_network(adapter_object, simple_connection=True)

    return True


def remove_process_module(adapter_object: adapters.ProductionSystemData) -> bool:
    """
    Function that removes a random process module from a random machine of the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if a process module was removed, False otherwise (if removing is not possible due to constraint violations).
    """
    possible_machines = adapters.get_production_resources(adapter_object)
    if not possible_machines:
        return False
    machine = random.choice(possible_machines)

    required_ids = set(get_required_process_ids(adapter_object))
    possible_processes = [
        process_module
        for process_module in get_possible_production_processes_IDs(adapter_object)
        if (
            isinstance(process_module, tuple)
            and all(process_id in required_ids for process_id in process_module)
        )
        or (isinstance(process_module, str) and process_module in required_ids)
    ]
    process_modules = get_grouped_processes_of_machine(machine, possible_processes)
    if not process_modules:
        return False
    process_module_to_delete = random.choice(process_modules)
    expanded_module = expand_process_ids_with_models(
        adapter_object, list(process_module_to_delete)
    )
    for process_instance in expanded_module:
        if process_instance in machine.process_ids:
            machine.process_ids.remove(process_instance)
    add_setup_states_to_machine(adapter_object, machine.ID)
    return True


def move_process_module(adapter_object: adapters.ProductionSystemData) -> bool:
    """
    Function that moves a random process module from a random machine to another random machine of the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if a process module was moved, False otherwise (if moving is not possible due to constraint violations).
    """
    possible_machines = adapters.get_production_resources(adapter_object)
    if not possible_machines or len(possible_machines) < 2:
        return False
    from_machine = random.choice(possible_machines)
    possible_machines.remove(from_machine)
    to_machine = random.choice(possible_machines)

    required_ids = set(get_required_process_ids(adapter_object))
    possible_processes = [
        process_module
        for process_module in get_possible_production_processes_IDs(adapter_object)
        if (
            isinstance(process_module, tuple)
            and all(process_id in required_ids for process_id in process_module)
        )
        or (isinstance(process_module, str) and process_module in required_ids)
    ]
    grouped_process_module_IDs = get_grouped_processes_of_machine(
        from_machine, possible_processes
    )
    if not grouped_process_module_IDs:
        return False
    process_module_to_move = random.choice(grouped_process_module_IDs)
    expanded_module = expand_process_ids_with_models(
        adapter_object, list(process_module_to_move)
    )
    if not expanded_module:
        return False
    for process_module in expanded_module:
        if process_module in from_machine.process_ids:
            from_machine.process_ids.remove(process_module)
    for process_module in expanded_module:
        if process_module not in to_machine.process_ids:
            to_machine.process_ids.append(process_module)
    add_setup_states_to_machine(adapter_object, from_machine.ID)
    add_setup_states_to_machine(adapter_object, to_machine.ID)
    return True


def update_production_resource_location(
    resource: resource_data.ResourceData, new_location: List[float]
) -> None:
    """
    Function that updates the location of a machine.

    Args:
        resource (resource_data.ResourceData): Machine to update.
        location (List[float]): New location of the machine.
    """
    resource.location = new_location


def move_machine(adapter_object: adapters.ProductionSystemData) -> bool:
    """
    Function that moves a random machine to a random position of the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if a machine was moved, False otherwise (if moving is not possible due to constraint violations).
    """
    possible_machines = adapters.get_production_resources(adapter_object)
    if not possible_machines:
        return False
    moved_machine = random.choice(possible_machines)
    possible_positions = deepcopy(adapter_object.scenario_data.options.positions)
    for machine in possible_machines:
        if machine.location in possible_positions:
            possible_positions.remove(machine.location)
    if not possible_positions:
        return False
    new_location = random.choice(possible_positions)
    update_production_resource_location(moved_machine, new_location)
    if any(isinstance(process, LinkTransportProcessData) for process in adapter_object.process_data):
        node_link_generation.generate_and_apply_network(adapter_object, simple_connection=True)
    return True


def add_primitive(adapter_object: adapters.ProductionSystemData) -> bool:
    """
    Function that adds a random primitive component to the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if an primitive component was added, False otherwise (if adding is not possible due to constraint violations).
    """
    required_primitives = get_required_primitives(adapter_object)
    primitive: StoredPrimitive = random.choice(required_primitives)
    storage_index = random.choice(range(len(primitive.quantity_in_storages)))
    queue = [
        queue
        for queue in adapter_object.port_data
        if queue.ID == primitive.storages[storage_index]
    ][0]
    if queue.capacity == primitive.quantity_in_storages[storage_index]:
        return False
    primitive.quantity_in_storages[storage_index] += 1
    return True


def remove_primitive(adapter_object: adapters.ProductionSystemData) -> bool:
    """
    Function that removes a random primitive component from the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if an primitive component was removed, False otherwise (if removing is not possible due to constraint violations).
    """
    required_primitives = get_required_primitives(adapter_object)
    primitive: StoredPrimitive = random.choice(required_primitives)
    storage_index = random.choice(range(len(primitive.storages)))
    if primitive.quantity_in_storages[storage_index] == 0:
        return False
    primitive.quantity_in_storages[storage_index] -= 1
    return True


def change_control_policy(adapter_object: adapters.ProductionSystemData) -> bool:
    """
    Function that changes the control policy of a random resource of the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if the control policy was changed, False otherwise (if changing is not possible due to constraint violations).
    """
    if not adapter_object.resource_data:
        return False
    resource = random.choice(adapter_object.resource_data)
    
    # Check if transport resource based on process types
    transport_process_ids = set(get_possible_transport_processes_IDs(adapter_object))
    is_transport = any(proc_id in transport_process_ids for proc_id in resource.process_ids)
    
    if is_transport:
        possible_control_policies = deepcopy(
            adapter_object.scenario_data.options.transport_controllers
        )
    else:
        possible_control_policies = deepcopy(
            adapter_object.scenario_data.options.machine_controllers
        )

    if not possible_control_policies or len(possible_control_policies) < 2:
        return False
    # Only remove if the current policy is in the list
    if resource.control_policy in possible_control_policies:
        possible_control_policies.remove(resource.control_policy)
    if not possible_control_policies:
        return False
    new_control_policy = random.choice(possible_control_policies)
    resource.control_policy = new_control_policy
    return True


def change_routing_policy(adapter_object: adapters.ProductionSystemData) -> None:
    """
    Function that changes the routing policy of a random source of the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.
    """
    source = random.choice(adapter_object.source_data)
    possible_routing_policies = deepcopy(
        adapter_object.scenario_data.options.routing_heuristics
    )
    if len(possible_routing_policies) < 2:
        return False
    possible_routing_policies.remove(source.routing_heuristic)
    source.routing_heuristic = random.choice(possible_routing_policies)
    return True


def get_mutation_operations(
    adapter_object: adapters.ProductionSystemData,
) -> List[Callable[[adapters.ProductionSystemData], bool]]:
    mutations_operations = []
    transformations = adapter_object.scenario_data.options.transformations
    for transformation in transformations:
        mutations_operations += TRANSFORMATIONS[transformation]
    mutations_operations = list(set(mutations_operations))
    return mutations_operations


def mutation(individual):
    mutation_operation = random.choice(get_mutation_operations(individual[0]))
    adapter_object = individual[0]
    if mutation_operation(adapter_object):
        individual[0].ID = str(uuid1())
    add_default_queues_to_resources(adapter_object, reset=False)
    clean_out_breakdown_states_of_resources(adapter_object)
    adjust_process_capacities(adapter_object)
    sync_resource_dependencies(adapter_object)

    return (individual,)


def arrange_machines(adapter_object: adapters.ProductionSystemData) -> None:
    possible_positions = deepcopy(adapter_object.scenario_data.options.positions)
    for machine in adapters.get_production_resources(adapter_object):
        new_location = random.choice(possible_positions)
        update_production_resource_location(machine, new_location)
        possible_positions.remove(new_location)


def get_random_production_capacity(
    adapter_object: adapters.ProductionSystemData,
) -> adapters.ProductionSystemData:
    """
    Function that adds a random number of machines to the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        adapters.ProductionSystemAdapter: Production system configuration with specified scenario data and added machines.
    """
    num_machines = (
        random.choice(range(adapter_object.scenario_data.constraints.max_num_machines))
        + 1
    )
    required_resource_ids = _get_resource_dependency_ids(adapter_object)
    original_transport_resources = adapters.get_transport_resources(adapter_object)
    original_production_resources = adapters.get_production_resources(adapter_object)

    adapter_object.resource_data = list(original_transport_resources)
    existing_ids = {resource.ID for resource in adapter_object.resource_data}
    for resource in original_production_resources:
        if resource.ID in required_resource_ids and resource.ID not in existing_ids:
            adapter_object.resource_data.append(resource)
            existing_ids.add(resource.ID)

    for _ in range(num_machines):
        add_machine(adapter_object)

    sync_resource_dependencies(adapter_object)
    return adapter_object


def get_random_transport_capacity(
    adapter_object: adapters.ProductionSystemData,
) -> adapters.ProductionSystemData:
    """
    Function that adds a random number of transport resources to the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        adapters.ProductionSystemAdapter: Production system configuration with specified scenario data and added transport resources.
    """
    num_transport_resources = (
        random.choice(
            range(adapter_object.scenario_data.constraints.max_num_transport_resources)
        )
        + 1
    )
    required_resource_ids = _get_resource_dependency_ids(adapter_object)
    original_production_resources = adapters.get_production_resources(adapter_object)
    original_transport_resources = adapters.get_transport_resources(adapter_object)

    adapter_object.resource_data = list(original_production_resources)
    existing_ids = {resource.ID for resource in adapter_object.resource_data}
    for resource in original_transport_resources:
        if resource.ID in required_resource_ids and resource.ID not in existing_ids:
            adapter_object.resource_data.append(resource)
            existing_ids.add(resource.ID)

    for _ in range(num_transport_resources):
        add_transport_resource(adapter_object)
    sync_resource_dependencies(adapter_object)
    delete_unused_conveyor_processes(adapter_object)
    return adapter_object


def get_random_primitive_capacity(
    adapter_object: adapters.ProductionSystemData,
) -> adapters.ProductionSystemData:
    required_primitives = get_required_primitives(adapter_object)
    available_storage_capacities = {
        queue.ID: queue.capacity for queue in adapter_object.port_data
    }
    for primitive in required_primitives:
        for storage_index, storage in enumerate(primitive.storages):
            if available_storage_capacities[storage] == 0:
                continue
            random_capacity = random.choice(
                range(1, available_storage_capacities[storage] + 1)
            )
            if available_storage_capacities[storage] - random_capacity < 0:
                random_capacity = available_storage_capacities[storage]
            primitive.quantity_in_storages[storage_index] = random_capacity
            available_storage_capacities[storage] -= random_capacity
    return adapter_object


def get_random_layout(
    adapter_object: adapters.ProductionSystemData,
) -> adapters.ProductionSystemData:
    """
    Function that randomly arranges the machines of the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        adapters.ProductionSystemAdapter: Production system configuration with specified scenario data and arranged machines.
    """
    possible_positions = deepcopy(adapter_object.scenario_data.options.positions)
    for machine in adapters.get_production_resources(adapter_object):
        new_location = random.choice(possible_positions)
        update_production_resource_location(machine, new_location)
        possible_positions.remove(new_location)
    if any(isinstance(process, LinkTransportProcessData) for process in adapter_object.process_data):    
        node_link_generation.generate_and_apply_network(adapter_object, simple_connection=True)
    return adapter_object


def get_random_control_policies(
    adapter_object: adapters.ProductionSystemData,
) -> adapters.ProductionSystemData:
    """
    Function that randomly assigns control policies to the machines and transport resources of the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        adapters.ProductionSystemAdapter: Production system configuration with specified scenario data and assigned control policies.
    """
    possible_production_control_policies = deepcopy(
        adapter_object.scenario_data.options.machine_controllers
    )
    if possible_production_control_policies:
        for machine in adapters.get_production_resources(adapter_object):
            machine.control_policy = random.choice(possible_production_control_policies)
    possible_transport_control_policies = deepcopy(
        adapter_object.scenario_data.options.transport_controllers
    )
    if possible_transport_control_policies:
        for transport_resource in adapters.get_transport_resources(adapter_object):
            transport_resource.control_policy = random.choice(
                possible_transport_control_policies
            )
    return adapter_object


def get_random_routing_logic(
    adapter_object: adapters.ProductionSystemData,
) -> adapters.ProductionSystemData:
    """
    Function that randomly assigns routing logics to the sources of the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        adapters.ProductionSystemAdapter: Production system configuration with specified scenario data and assigned routing logics.
    """
    possible_routing_logics = deepcopy(
        adapter_object.scenario_data.options.routing_heuristics
    )
    for source in adapter_object.source_data:
        source.routing_heuristic = random.choice(possible_routing_logics)
    return adapter_object


def random_configuration(
    baseline: adapters.ProductionSystemData,
) -> adapters.ProductionSystemData:
    """
    Function that creates a random configuration based on a baseline configuration.

    Args:
        baseline (adapters.ProductionSystemAdapter): Baseline configuration.

    Returns:
        adapters.ProductionSystemAdapter: Random configuration based on a baseline configuration.
    """
    transformations = baseline.scenario_data.options.transformations
    adapter_object = baseline.model_copy(deep=True)
    adapter_object.ID = str(uuid1())
    if scenario_data.ReconfigurationEnum.PRODUCTION_CAPACITY in transformations:
        get_random_production_capacity(adapter_object)
    if scenario_data.ReconfigurationEnum.TRANSPORT_CAPACITY in transformations:
        get_random_transport_capacity(adapter_object)
    if scenario_data.ReconfigurationEnum.PRIMITIVE_CAPACITY in transformations:
        get_random_primitive_capacity(adapter_object)
    if (
        scenario_data.ReconfigurationEnum.LAYOUT in transformations
        and scenario_data.ReconfigurationEnum.PRODUCTION_CAPACITY not in transformations
    ):
        get_random_layout(adapter_object)
    if scenario_data.ReconfigurationEnum.SEQUENCING_LOGIC in transformations and (
        scenario_data.ReconfigurationEnum.PRODUCTION_CAPACITY not in transformations
        or scenario_data.ReconfigurationEnum.TRANSPORT_CAPACITY not in transformations
    ):
        get_random_control_policies(adapter_object)
    if scenario_data.ReconfigurationEnum.ROUTING_LOGIC in transformations:
        get_random_routing_logic(adapter_object)
    
    add_default_queues_to_resources(adapter_object, reset=False)
    if any(isinstance(process, LinkTransportProcessData) for process in adapter_object.process_data):    
        node_link_generation.generate_and_apply_network(adapter_object, simple_connection=True)
    clean_out_breakdown_states_of_resources(adapter_object)
    adjust_process_capacities(adapter_object)
    sync_resource_dependencies(adapter_object)

    if not check_valid_configuration(adapter_object, baseline):
        return
    return adapter_object


def get_random_configuration_asserted(
    baseline: adapters.ProductionSystemData,
) -> adapters.ProductionSystemData:
    """
    Function that creates a random configuration based on a baseline configuration.

    Args:
        baseline (adapters.ProductionSystemAdapter): Baseline configuration.

    Returns:
        adapters.ProductionSystemAdapter: Random configuration based on a baseline configuration.
    """
    invalid_configuration_counter = 0
    while True:
        adapter_object = random_configuration(baseline)
        if adapter_object:
            return adapter_object
        invalid_configuration_counter += 1
        if invalid_configuration_counter % 50 == 0: 
            logging.info(
                f"More than {invalid_configuration_counter} invalid configurations were created in a row. Are you sure that the constraints are correct and not too strict?"
            )


def random_configuration_with_initial_solution(
    initial_adapters: List[adapters.ProductionSystemData],
    max_manipulations: int = 3,
    new_solution_probability: float = 0.1,
) -> adapters.ProductionSystemData:
    """
    Creates a new configuration based on a list of initial solutions.
    With probability new_solution_probability, a completely new configuration is generated.
    Otherwise, a randomly chosen initial adapter is manipulated by applying a random number
    (from 1 to max_manipulations) of mutation operations.

    Args:
        initial_adapters (List[adapters.ProductionSystemAdapter]): List of initial solutions.
        max_manipulations (int, optional): Maximum number of mutation operations to apply. Defaults to 3.
        new_solution_probability (float, optional): Chance to generate a completely new configuration. Defaults to 0.1.

    Returns:
        adapters.ProductionSystemAdapter: A new configuration derived either by manipulation or by complete randomization.
    """
    invalid_configuration_counter = 0

    while True:
        # Select a baseline adapter from the list.
        baseline = random.choice(initial_adapters)
        # With a given probability, generate a completely new random configuration.
        if random.random() < new_solution_probability:
            adapter_object = random_configuration(baseline)
            if not adapter_object:
                invalid_configuration_counter += 1
                continue
            return adapter_object

        # Otherwise, start with a deep copy of the baseline and apply random manipulations.
        adapter_object = baseline.model_copy(deep=True)
        num_manipulations = random.randint(0, max_manipulations)

        mutation_ops = get_mutation_operations(adapter_object)
        successful_mutations = 0
        for _ in range(num_manipulations):
            mutation_op = random.choice(mutation_ops)
            # Apply the chosen mutation operation.
            if not mutation_op(adapter_object):
                break
            successful_mutations += 1
            add_default_queues_to_resources(adapter_object, reset=False)
            clean_out_breakdown_states_of_resources(adapter_object)
            adjust_process_capacities(adapter_object)
            sync_resource_dependencies(adapter_object)

        # Update the adapter's ID to mark the change.
        adapter_object.ID = str(uuid1())

        # Fallback: if the manipulated configuration is not valid, generate a completely new one.
        if successful_mutations == num_manipulations and check_valid_configuration(
            adapter_object, baseline
        ):
            sync_resource_dependencies(adapter_object)
            return adapter_object
        invalid_configuration_counter += 1
        if invalid_configuration_counter % 50 == 0:
            logging.warning(
                f"More than {invalid_configuration_counter} invalid configurations were created in a row. Are you sure that the constraints are correct and not too strict?"
            )


def configuration_capacity_based(
    baseline: adapters.ProductionSystemData, cap_target: float = 0.65
) -> adapters.ProductionSystemData:
    """
    Function that creates a smart random configuration based on capacity requirements.

    This approach:
    1. Calculates product arrival rates
    2. Determines process requirements for each product
    3. Calculates expected utilization for each process
    4. Groups processes efficiently on resources to meet target capacity

    Args:
        baseline (adapters.ProductionSystemData): Baseline configuration
        cap_target (float): Target utilization for resources (default: 0.65)

    Returns:
        adapters.ProductionSystemData: Capacity-optimized configuration
    """
    # Create a copy of the baseline configuration
    adapter_object = baseline.model_copy(deep=True)
    adapter_object.ID = str(uuid1())

    # Get mapping of processes and time models
    # NOTE: We do NOT initialize a runner here because it would validate the configuration,
    # which may fail if required processes are not yet assigned to machines.
    # Instead, we work directly with the data and use process matching later only if needed.
    time_models_per_id = {t.ID: t for t in adapter_object.time_model_data}
    processes_per_id = {p.ID: p for p in adapter_object.process_data}

    # Calculate product arrival rates from sources
    product_arrival_rates = {}
    for source in adapter_object.source_data:
        time_model_data = time_models_per_id.get(source.time_model_id)
        product_id = source.product_type
        if time_model_data:
            # Use mean of interarrival time model
            mean_interarrival = time_model_data.location
            rate = 1.0 / mean_interarrival if mean_interarrival > 0 else 0
            product_arrival_rates[product_id] = (
                product_arrival_rates.get(product_id, 0) + rate
            )

    # Helper function for transport time calculation (simplified - no runner needed)
    def estimate_transport_time(time_model_data: TIME_MODEL_DATA) -> float:
        """Estimate average transport time based on time model type."""
        if isinstance(time_model_data, DistanceTimeModelData):
            # For distance-based models, use a reasonable average distance
            # Assuming typical distance between positions
            avg_distance = 10.0  # Reasonable default
            return avg_distance / time_model_data.speed + time_model_data.reaction_time
        else:
            # For other time models, use the location parameter
            return time_model_data.location

    @dataclass
    class ProductProcessRequirement:
        product_id: str
        process_id: str
        time_model_id: str
        expecteded_time: float
        num_instances: float
        product_arrival_rate: float

    # Calculate process requirements
    process_requirements = {}
    transport_requirements = {}

    # Process products to determine requirements
    for product in adapter_object.product_data:
        if product.ID not in product_arrival_rates:
            continue

        # Calculate transport requirements
        transport_process = processes_per_id.get(product.transport_process)
        if transport_process:
            transport_time_model = time_models_per_id.get(
                transport_process.time_model_id
            )
            if transport_time_model:
                transport_time = estimate_transport_time(transport_time_model)
                num_transports = 2 * (
                    len(product.processes) + 2
                )  # Source, sink, and pickup/dropoff

                transport_requirements[product.ID] = ProductProcessRequirement(
                    product.ID,
                    transport_process.ID,
                    transport_process.time_model_id,
                    transport_time,
                    num_transports,
                    product_arrival_rates[product.ID],
                )

        # Calculate production process requirements
        # SIMPLIFIED: We just use the process IDs directly from the product
        # This allows us to work with incomplete baselines (processes not yet assigned to machines)
        for process_id in product.processes:
            required_process_data = processes_per_id.get(process_id)

            if not required_process_data:
                continue

            # Use the process directly (no need to find compatible ones)
            time_model_id = required_process_data.time_model_id
            time_model = time_models_per_id.get(time_model_id)
            
            if not time_model:
                continue

            process_requirements[product.ID + ":" + process_id] = (
                ProductProcessRequirement(
                    product.ID,
                    process_id,
                    time_model_id,
                    time_model.location,
                    1,
                    product_arrival_rates[product.ID],
                )
            )

    # Combine requirements
    all_requirements = {**process_requirements, **transport_requirements}
    requirements_df = pd.DataFrame(all_requirements.values())
    requirements_df["requested_rate"] = (
        requirements_df["num_instances"] * requirements_df["product_arrival_rate"]
    )

    # Calculate utilization per process
    requested_rate = requirements_df.groupby("process_id").sum(numeric_only=True)[
        "requested_rate"
    ]
    df_per_process = requirements_df[
        ["process_id", "time_model_id", "expecteded_time"]
    ].drop_duplicates()

    df_per_process = pd.merge(
        df_per_process,
        requested_rate.rename("requested_rate"),
        on="process_id",
        how="left",
    )

    df_per_process["expected_service_rate"] = 1 / df_per_process["expecteded_time"]
    df_per_process["utilization"] = (
        df_per_process["requested_rate"] / df_per_process["expected_service_rate"]
    )

    # Consider breakdown times for resources
    breakdown_states_data = [
        state
        for state in adapter_object.state_data
        if isinstance(state, BreakDownStateData)
    ]

    # Calculate downtime rates
    down_time_breakdown_state = {}
    for state_data in breakdown_states_data:
        if not state_data.ID in ["BSM", "BST", "BSP"]:
            continue

        breakdown_time_model = time_models_per_id.get(state_data.time_model_id)
        repair_time_model = time_models_per_id.get(state_data.repair_time_model_id)

        if breakdown_time_model and repair_time_model:
            mtbf = breakdown_time_model.location
            mttr = repair_time_model.location
            downtime = mttr / (mtbf + mttr)
            down_time_breakdown_state[state_data.ID] = downtime

    # Add downtime to utilization calculation
    df_per_process["is_transport_process"] = df_per_process["process_id"].apply(
        lambda x: isinstance(processes_per_id[x], TransportProcessData)
    )

    # Apply downtime factors
    if "BST" in down_time_breakdown_state:
        df_per_process.loc[df_per_process["is_transport_process"], "down_time"] = (
            down_time_breakdown_state["BST"]
        )
    else:
        df_per_process.loc[df_per_process["is_transport_process"], "down_time"] = (
            0.1  # Default
        )

    if "BSM" in down_time_breakdown_state:
        df_per_process.loc[~df_per_process["is_transport_process"], "down_time"] = (
            down_time_breakdown_state["BSM"]
        )
    else:
        df_per_process.loc[~df_per_process["is_transport_process"], "down_time"] = (
            0.15  # Default
        )

    # Calculate effective utilization considering downtime
    df_per_process["considering_downtime_utilization"] = df_per_process[
        "utilization"
    ] / (1 - df_per_process["down_time"])

    def consider_compound_processes(
        compound_processes: List[CompoundProcessData],
        df_per_process: pd.DataFrame,
    ) -> None:
        """
        Combines compound processes into a single process in the dataframe.

        Args:
            compound_processes (List[CompoundProcessData]): List of compound processes to combine
            df_per_process (pd.DataFrame): Dataframe containing process data

        Returns:
            None: Modifies the dataframe in place
        """
        for compound_process in compound_processes:
            df_per_process.loc[
                df_per_process["process_id"].isin(compound_process.process_ids), "process_id"
            ] = compound_process.ID

    compound_processes = [
        p for p in baseline.process_data if isinstance(p, CompoundProcessData)
    ]
    if compound_processes:
        consider_compound_processes(compound_processes, df_per_process)
        df_per_process = (
            df_per_process.groupby("process_id", as_index=False)
            .sum(numeric_only=True)
            .reset_index()
        )

    # Function to combine processes efficiently
    def combine_processes(
        df: pd.DataFrame, max_process_modules: int, cap_target: float = cap_target
    ):
        """
        Combines processes from a dataframe into efficient groups based on utilization.

        Args:
            df (pd.DataFrame): The input table with process details
            max_process_modules (int): Maximum number of process modules per resource
            cap_target (float): Target capacity utilization per resource

        Returns:
            list of dict: Process groupings
        """
        # Convert rows to a list of dictionaries and shuffle randomly
        rows = df.to_dict(orient="records")
        random.shuffle(rows)

        groups = []
        current_group = []
        current_sum = 0.0
        current_floor = None

        for row in rows:
            util = row["considering_downtime_utilization"]
            pid = row["process_id"]
            process = processes_per_id.get(pid)

            # Handle transport processes separately
            if isinstance(process, TransportProcessData):
                groups.append({"process_ids": [pid], "group_total_utilization": util})
                continue

            # Start a new group if needed
            if current_floor is None:
                current_group.append(pid)
                current_sum = util
                current_floor = math.floor(current_sum)
            else:
                new_sum = current_sum + util
                # Check if adding would exceed target capacity
                open_ratio = new_sum - int(new_sum)
                if math.floor(new_sum) == current_floor and open_ratio < cap_target and len(current_group) < max_process_modules:
                    # If within capacity target, add to current group
                    current_group.append(pid)
                    current_sum = new_sum
                else:
                    # Otherwise finish current group and start a new one
                    groups.append(
                        {
                            "process_ids": current_group,
                            "group_total_utilization": current_sum,
                        }
                    )
                    # Start a new group
                    current_group = [pid]
                    current_sum = util
                    current_floor = math.floor(current_sum)

        # Add the last group if not empty
        if current_group:
            groups.append(
                {"process_ids": current_group, "group_total_utilization": current_sum}
            )

        return groups

    # Combine processes into resource groups
    combined_processes = combine_processes(df_per_process, max_process_modules=adapter_object.scenario_data.constraints.max_num_processes_per_machine)

    # Ensure all required processes are included
    # Get all processes that should be covered (from products)
    required_process_ids = set()
    for product in adapter_object.product_data:
        required_process_ids.update(product.processes)
    
    # Get all processes currently in combined_processes
    covered_process_ids = set()
    for group in combined_processes:
        covered_process_ids.update(group["process_ids"])
    
    # Add missing processes as individual resources with PRIORITY (insert at beginning)
    missing_process_ids = required_process_ids - covered_process_ids
    for missing_pid in missing_process_ids:
        # Add each missing process as a separate resource group with minimal utilization
        # Insert at the beginning to ensure they get created before hitting resource limits
        combined_processes.insert(0, {
            "process_ids": [missing_pid],
            "group_total_utilization": cap_target  # Use cap_target to ensure at least one resource is created
        })

    # Create resources based on the combined process groups
    adapter_object.resource_data = []
    all_possible_positions = adapter_object.scenario_data.options.positions.copy()
    possible_positions = all_possible_positions.copy()
    
    # Track resource counts to respect constraints
    max_production_resources = adapter_object.scenario_data.constraints.max_num_machines
    max_transport_resources = adapter_object.scenario_data.constraints.max_num_transport_resources
    production_resource_count = 0
    transport_resource_count = 0
    
    compound_processes_per_id = {
        p.ID: p for p in compound_processes
    }
    
    # PHASE 1: Ensure each process group has at least ONE resource (to cover all required processes)
    skipped_groups = []
    for group in combined_processes:
        process_data = group["process_ids"]
        if not process_data:
            continue

        sample_process = processes_per_id.get(process_data[0])
        if isinstance(sample_process, TransportProcessData):
            # Check transport resource limit
            if transport_resource_count >= max_transport_resources:
                skipped_groups.append(process_data)
                continue
                
            # Create transport resource
            resource = resource_data.ResourceData(
                location=[0, 0],
                ID=str(uuid1()),
                description="",
                capacity=1,
                can_move=True, #TODO: adapt to the given production system
                control_policy="FIFO",
                controller=resource_data.ControllerEnum.PipelineController,
                process_ids=process_data,
            )
            transport_resource_count += 1
            adapter_object.resource_data.append(resource)
        else:
            # Check production resource limit
            if production_resource_count >= max_production_resources:
                skipped_groups.append(process_data)
                continue
                
            # Create production resource
            if possible_positions:
                position = possible_positions.pop()
            else:
                # If we run out of positions, reuse from the original list
                position = random.choice(all_possible_positions)

            updated_process_data = []
            for process_id in process_data:
                if process_id in compound_processes_per_id:
                    compound_process = compound_processes_per_id[process_id]
                    updated_process_data.extend(compound_process.process_ids)
                else:
                    updated_process_data.append(process_id)
            updated_process_data = expand_process_ids_with_models(
                adapter_object, updated_process_data
            )

            resource = resource_data.ResourceData(
                ID=str(uuid1()),
                description="",
                process_ids=updated_process_data,
                location=position,
                capacity=1,
                controller=resource_data.ControllerEnum.PipelineController,
                control_policy="FIFO",
            )
            production_resource_count += 1
            adapter_object.resource_data.append(resource)
    
    
    # PHASE 2: Add additional resources based on utilization (if capacity allows)
    for group in combined_processes:
        num_additional_resources = int(group["group_total_utilization"] / cap_target)  # Already created 1, so subtract 1 from the total
        
        for num in range(num_additional_resources):
            process_data = group["process_ids"]
            if not process_data:
                continue

            sample_process = processes_per_id.get(process_data[0])
            if isinstance(sample_process, TransportProcessData):
                # Check transport resource limit
                if transport_resource_count >= max_transport_resources:
                    break
                    
                # Create transport resource
                resource = resource_data.ResourceData(
                    location=[0, 0],
                    ID=str(uuid1()),
                    description="",
                    capacity=1,
                    can_move=True, #TODO: adapt to the given production system
                    control_policy="FIFO",
                    controller=resource_data.ControllerEnum.PipelineController,
                    process_ids=process_data,
                )
                transport_resource_count += 1
                adapter_object.resource_data.append(resource)
            else:
                # Check production resource limit
                if production_resource_count >= max_production_resources:
                    break
                    
                # Create production resource
                if possible_positions:
                    position = possible_positions.pop()
                else:
                    # If we run out of positions, reuse from the original list
                    position = random.choice(all_possible_positions)

                updated_process_data = []
                for process_id in process_data:
                    if process_id in compound_processes_per_id:
                        compound_process = compound_processes_per_id[process_id]
                        updated_process_data.extend(compound_process.process_ids)
                    else:
                        updated_process_data.append(process_id)
                updated_process_data = expand_process_ids_with_models(
                    adapter_object, updated_process_data
                )

                resource = resource_data.ResourceData(
                    ID=str(uuid1()),
                    description="",
                    process_ids=updated_process_data,
                    location=position,
                    capacity=1,
                    controller=resource_data.ControllerEnum.PipelineController,
                    control_policy="FIFO",
                )
                production_resource_count += 1
                adapter_object.resource_data.append(resource)

    # Finalize configuration
    adapter_object = add_default_queues_to_resources(adapter_object)
    clean_out_breakdown_states_of_resources(adapter_object)
    adjust_process_capacities(adapter_object)
    sync_resource_dependencies(adapter_object)

    return adapter_object


def configuration_capacity_based_asserted(
    baseline: adapters.ProductionSystemData, cap_target: float = 0.65
) -> adapters.ProductionSystemData:
    """
    Creates a capacity-based random configuration and ensures it meets all constraints.

    Args:
        baseline (adapters.ProductionSystemData): Baseline configuration
        cap_target (float): Target utilization for resources (default: 0.65)

    Returns:
        adapters.ProductionSystemData: Valid capacity-optimized configuration
    """
    invalid_configuration_counter = 0
    max_attempts = 500  # Add maximum attempts to prevent infinite looping
    last_error = None
    while invalid_configuration_counter < max_attempts:
        try:
            adapter_object = configuration_capacity_based(baseline, cap_target)
            # Use verbose logging for the first few attempts to debug
            verbose = invalid_configuration_counter < 3
            if check_valid_configuration(adapter_object, baseline, verbose=verbose):
                return adapter_object
            else:
                last_error = "Configuration validation failed"
                if verbose:
                    logging.warning(f"Configuration validation failed on attempt {invalid_configuration_counter + 1}")
        except Exception as e:
            last_error = str(e)
            if invalid_configuration_counter < 3:
                logging.warning(f"Error during configuration creation on attempt {invalid_configuration_counter + 1}: {e}")

        invalid_configuration_counter += 1
        if invalid_configuration_counter % 10 == 0:
            # After 10 failed attempts, adjust capacity target
            cap_target *= 0.95
            logging.info(f"Adjusting capacity target to {cap_target}")

        if invalid_configuration_counter % 100 == 0:
            logging.warning(
                f"Created {invalid_configuration_counter} invalid configurations based on capacity."
            )
    
    # If we reach here, we've failed too many times - raise an error with diagnostic info
    raise ValueError(f"Failed to create valid configuration after {max_attempts} attempts. Last error: {last_error}")


def random_configuration_capacity_based(
    baseline: adapters.ProductionSystemData, cap_target: float = 0.65, mutation_probability: float = 0.5
) -> adapters.ProductionSystemData:
    """
    Creates a capacity-based configuration with optional mutation.
    
    Args:
        baseline (adapters.ProductionSystemData): Baseline configuration
        cap_target (float): Target utilization for resources (default: 0.65)
        mutation_probability (float): Probability to mutate the configuration (default: 0.5)
        
    Returns:
        adapters.ProductionSystemData: Capacity-optimized configuration (possibly mutated)
    """
    smart_configuration = configuration_capacity_based_asserted(baseline, cap_target)
    if random.random() > mutation_probability:
        return smart_configuration
    return random_configuration_with_initial_solution(
        [smart_configuration],
        max_manipulations=3,
        new_solution_probability=0.1,
    )


TRANSFORMATIONS = {
    scenario_data.ReconfigurationEnum.PRODUCTION_CAPACITY: [
        add_machine,
        remove_machine,
        move_machine,
        change_control_policy,
        add_process_module,
        remove_process_module,
        move_process_module,
    ],
    scenario_data.ReconfigurationEnum.TRANSPORT_CAPACITY: [
        add_transport_resource,
        remove_transport_resource,
    ],
    scenario_data.ReconfigurationEnum.PRIMITIVE_CAPACITY: [
        add_primitive,
        remove_primitive,
    ],
    scenario_data.ReconfigurationEnum.LAYOUT: [move_machine],
    scenario_data.ReconfigurationEnum.SETUP: [move_process_module],
    scenario_data.ReconfigurationEnum.SEQUENCING_LOGIC: [change_control_policy],
    scenario_data.ReconfigurationEnum.ROUTING_LOGIC: [change_routing_policy],
}

# Save initial state for cleanup
_INITIAL_TRANSFORMATIONS = {
    key: value.copy() for key, value in TRANSFORMATIONS.items()
}


def add_transformation_operation(
    transformation: scenario_data.ReconfigurationEnum,
    operation: Callable[[adapters.ProductionSystemData], bool],
) -> None:
    """
    Function that adds a transformation operation to the transformation dictionary.

    Args:
        transformation (scenario_data.ReconfigurationEnum): Transformation to add the operation to.
        operation (Callable[[adapters.ProductionSystemAdapter], bool]): Operation to add to the transformation.
    """
    if transformation in TRANSFORMATIONS:
        TRANSFORMATIONS[transformation].append(operation)


def reset_transformations() -> None:
    """
    Reset TRANSFORMATIONS to its initial state, removing any operations added via add_transformation_operation.
    This is useful for test cleanup to avoid test pollution.
    """
    global TRANSFORMATIONS
    TRANSFORMATIONS = {
        key: value.copy() for key, value in _INITIAL_TRANSFORMATIONS.items()
    }
