"""
Module containts utility functions for the optimization module. These functions can be used to change the production system configuration and evaluate its performance.
"""

from __future__ import annotations

import random
from copy import deepcopy
from typing import Dict, List, Union, Tuple, Literal, Callable
from enum import Enum
import logging
logger = logging.getLogger(__name__)
from uuid import uuid1
from collections.abc import Iterable
from pydantic import parse_obj_as

from prodsys import adapters, runner
from prodsys.adapters.adapter import add_default_queues_to_resources
from prodsys.adapters.adapter import assert_no_redudant_locations
from prodsys.adapters.adapter import assert_required_processes_in_resources_available
from prodsys.adapters.adapter import get_possible_production_processes_IDs, get_possible_transport_processes_IDs
from prodsys.util.post_processing import PostProcessor
from prodsys.models import (
    resource_data,
    state_data,
    processes_data,
    performance_indicators,
    scenario_data,
    time_model_data
)
from prodsys.util.util import flatten
from prodsys import optimization


class BreakdownStateNamingConvention(str, Enum):
    MACHINE_BREAKDOWN_STATE = "BSM"
    TRANSPORT_RESOURCE_BREAKDOWN_STATE = "BST"
    PROCESS_MODULE_BREAKDOWN_STATE = "BSP"


def get_breakdown_state_ids_of_machine_with_processes(
    processes: List[str],
) -> List[str]:
    # state_ids = [BreakdownStateNamingConvention.MACHINE_BREAKDOWN_STATE] + len(
    #     processes
    # ) * [BreakdownStateNamingConvention.PROCESS_MODULE_BREAKDOWN_STATE]
    state_ids = [BreakdownStateNamingConvention.MACHINE_BREAKDOWN_STATE]
    return state_ids


def check_breakdown_state_available(adapter_object: adapters.ProductionSystemAdapter, breakdown_state_id: str) -> bool:
    """
    Function that checks if breakdown states are available in the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if breakdown states are available, False otherwise.
    """
    breakdown_state_ids = set([
        state.ID
        for state in adapter_object.state_data
        if isinstance(state, state_data.BreakDownStateData) or isinstance(state, state_data.ProcessBreakDownStateData)
    ])
    if breakdown_state_id not in breakdown_state_ids:
        return False
    return True

def check_breakdown_states_available(adapter_object: adapters.ProductionSystemAdapter) -> bool:
    """
    Function that checks if breakdown states are available in the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if breakdown states are available, False otherwise.
    """
    if (
        not check_breakdown_state_available(adapter_object, BreakdownStateNamingConvention.MACHINE_BREAKDOWN_STATE)
        or not check_breakdown_state_available(adapter_object, BreakdownStateNamingConvention.TRANSPORT_RESOURCE_BREAKDOWN_STATE)
        # or not check_breakdown_state_available(adapter_object, BreakdownStateNamingConvention.PROCESS_MODULE_BREAKDOWN_STATE)
    ):
        return False
    return True


def check_heterogenous_time_models(time_models: List[time_model_data.TIME_MODEL_DATA]) -> bool:
    """
    Function that checks if heterogenous time models are present in the list.

    Args:
        time_models (List[time_model_data.TIME_MODEL_DATA]): List of time models.

    Returns:
        bool: True if heterogenous time models are available, False otherwise.
    """
    if all(isinstance(time_model, time_model_data.FunctionTimeModelData) for time_model in time_models):
        parameters = []
        for time_model in time_models:
            parameters.append((round(time_model.location), round(time_model.scale), time_model.distribution_function))
        if len(set(parameters)) == 1:
            return True
    elif all(isinstance(time_model, time_model_data.SequentialTimeModelData) for time_model in time_models):
        sequences = []
        for time_model in time_models:
            sequences.append(tuple(time_model.sequence))
        if len(set(sequences)) == 1:
            return True
    elif all(isinstance(time_model, time_model_data.ManhattanDistanceTimeModelData) for time_model in time_models):
        parameters = []
        for time_model in time_models:
            parameters.append((time_model.speed, time_model.reaction_time))
        if len(set(parameters)) == 1:
            return True
    return False


def check_states_for_heterogenous_time_models(states: List[Union[state_data.BreakDownStateData, state_data.ProcessBreakDownStateData]], adapter_object: adapters.ProductionSystemAdapter) -> bool:
    """
    Function that checks if the states have heterogenous time models.

    Args:
        states (List[Union[state_data.BreakDownStateData, state_data.ProcessBreakDownStateData]]): List of states.

    Returns:
        bool: True if the states are compatible, False otherwise.
    """
    all_time_models = adapter_object.time_model_data
    breakdown_time_models = []
    repair_time_models = []
    for state in states:
        breakdown_time_models.append([time_model for time_model in all_time_models if time_model.ID == state.time_model_id].pop())
        repair_time_models.append([time_model for time_model in all_time_models if time_model.ID == state.repair_time_model_id].pop())
    return (check_heterogenous_time_models(breakdown_time_models) and check_heterogenous_time_models(repair_time_models))


def create_default_breakdown_states(adapter_object: adapters.ProductionSystemAdapter):
    logger.info(f"Trying to create default breakdown states.")
    breakdown_states = [
        state
        for state in adapter_object.state_data
        if isinstance(state, state_data.BreakDownStateData)
    ]
    # process_breakdown_states = [state for state in adapter_object.state_data if isinstance(state, state_data.ProcessBreakDownStateData)]
    machines = adapters.get_machines(adapter_object)
    transport_resources = adapters.get_transport_resources(adapter_object)
    machine_breakdown_states = [state for state in breakdown_states if any(state.ID in machine.state_ids for machine in machines)]
    transport_resource_breakdown_states = [state for state in breakdown_states if any(state.ID in transport_resource.state_ids for transport_resource in transport_resources)]
    # process_breakdown_states = [state for state in process_breakdown_states if any(state.ID in machine.state_ids and state.process_id in machine.process_ids for machine in machines)]
    if machine_breakdown_states and not check_breakdown_state_available(adapter_object, BreakdownStateNamingConvention.MACHINE_BREAKDOWN_STATE):
        if not check_states_for_heterogenous_time_models(machine_breakdown_states, adapter_object):
            raise ValueError(f"The machine breakdown states are not heterogenous and it is not ambiguous which state should be the Breakdownstate. Please check the time models or define a distinct machine breakdown state called {BreakdownStateNamingConvention.MACHINE_BREAKDOWN_STATE}.")
        machine_breakdown_state = machine_breakdown_states[0].model_copy(deep=True)
        machine_breakdown_state.ID = BreakdownStateNamingConvention.MACHINE_BREAKDOWN_STATE
        adapter_object.state_data.append(machine_breakdown_state)
        logger.info(f"Added default breakdown state for production resources to the production system.")
    if transport_resource_breakdown_states and not check_breakdown_state_available(adapter_object, BreakdownStateNamingConvention.TRANSPORT_RESOURCE_BREAKDOWN_STATE):
        if not check_states_for_heterogenous_time_models(transport_resource_breakdown_states, adapter_object):
            raise ValueError(f"The transport resource breakdown states are not heterogenous and it is not ambiguous which state should be the Breakdownstate. Please check the time models or define a distinct transport resource breakdown state called {BreakdownStateNamingConvention.TRANSPORT_RESOURCE_BREAKDOWN_STATE}.")
        transport_resource_breakdown_state = transport_resource_breakdown_states[0].model_copy(deep=True)
        transport_resource_breakdown_state.ID = BreakdownStateNamingConvention.TRANSPORT_RESOURCE_BREAKDOWN_STATE
        adapter_object.state_data.append(transport_resource_breakdown_state)
        logger.info(f"Added default breakdown state for transport resources to the production system.")
    # TODO: add later logic for adding breakdown states for process modules automatically again if problems with process id reworked
    # if process_breakdown_states and not check_breakdown_state_available(adapter_object, BreakdownStateNamingConvention.PROCESS_MODULE_BREAKDOWN_STATE):
    #     if not check_states_for_heterogenous_time_models(process_breakdown_states, adapter_object):
    #         raise ValueError(f"The process breakdown states are not heterogenous and it is not ambiguous which state should be the Breakdownstate. Please check the time models or define a distinct process breakdown state called {BreakdownStateNamingConvention.PROCESS_MODULE_BREAKDOWN_STATE}.")
    #     process_breakdown_state = process_breakdown_states[0].model_copy()
    #     process_breakdown_state.ID = BreakdownStateNamingConvention.PROCESS_MODULE_BREAKDOWN_STATE
    #     adapter_object.state_data.append(process_breakdown_state)
    #     logger.info(f"Added default breakdown state for process modules to the production system.")

def clean_out_breakdown_states_of_resources(
    adapter_object: adapters.ProductionSystemAdapter,
):
    for resource in adapter_object.resource_data:
        if isinstance(resource, resource_data.ProductionResourceData) and any(
            True
            for state in adapter_object.state_data
            if state.ID == BreakdownStateNamingConvention.MACHINE_BREAKDOWN_STATE
            # or state.ID == BreakdownStateNamingConvention.PROCESS_MODULE_BREAKDOWN_STATE
        ):  
            resource.state_ids = get_breakdown_state_ids_of_machine_with_processes(
                resource.process_ids
            )
        elif isinstance(resource, resource_data.TransportResourceData) and any(
            True
            for state in adapter_object.state_data
            if state.ID
            == BreakdownStateNamingConvention.TRANSPORT_RESOURCE_BREAKDOWN_STATE
        ):
            resource.state_ids = [
                BreakdownStateNamingConvention.TRANSPORT_RESOURCE_BREAKDOWN_STATE
            ]


def get_weights(
    adapter: adapters.ProductionSystemAdapter, direction: Literal["min", "max"]
) -> Tuple[float, ...]:
    """
    Get the weights for the objectives of the optimization from an adapter.

    Args:
        adapter (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.
        direction (Literal[&quot;min&quot;, &quot;max&quot;]): Optimization target direction of the optimizer.

    Returns:
        Tuple[float, ...]: Tuple of weights for the objectives.
    """
    weights = []
    for objective in adapter.scenario_data.objectives:
        kpi = parse_obj_as(performance_indicators.KPI_UNION, {"name": objective.name})
        if kpi.target != direction:
            weights.append(objective.weight * -1)
        else:
            weights.append(objective.weight)
    return tuple(weights)


def crossover(ind1, ind2):
    ind1[0].ID = str(uuid1())
    ind2[0].ID = str(uuid1())

    crossover_type = random.choice(["machine", "partial_machine", "transport_resource"])
    adapter1: adapters.ProductionSystemAdapter = ind1[0]
    adapter2: adapters.ProductionSystemAdapter = ind2[0]
    machines_1 = adapters.get_machines(adapter1)
    machines_2 = adapters.get_machines(adapter2)
    transport_resources_1 = adapters.get_transport_resources(adapter1)
    transport_resources_2 = adapters.get_transport_resources(adapter2)
    if "machine" in crossover_type:
        adapter1.resource_data = transport_resources_1
        adapter2.resource_data = transport_resources_2
        if crossover_type == "partial_machine":
            min_length = min(len(machines_1),len(machines_2))
            machines_1 = machines_1[:min_length] + machines_2[min_length:]
            machines_2 = machines_2[:min_length] + machines_1[min_length:]
        adapter1.resource_data += machines_2
        adapter2.resource_data += machines_1

    if crossover_type == "transport_resource":
        adapter1.resource_data = machines_1 + transport_resources_2
        adapter2.resource_data = machines_2 + transport_resources_1

    add_default_queues_to_resources(adapter1)
    add_default_queues_to_resources(adapter2)
    clean_out_breakdown_states_of_resources(adapter1)
    clean_out_breakdown_states_of_resources(adapter2)
    adjust_process_capacities(adapter1)
    adjust_process_capacities(adapter2)

    return ind1, ind2


def get_mutation_operations(
    adapter_object: adapters.ProductionSystemAdapter,
) -> List[Callable[[adapters.ProductionSystemAdapter], bool]]:
    mutations_operations = []
    transformations = adapter_object.scenario_data.options.transformations
    if scenario_data.ReconfigurationEnum.PRODUCTION_CAPACITY in transformations:
        mutations_operations.append(add_machine)
        mutations_operations.append(remove_machine)
        mutations_operations.append(move_machine)
        mutations_operations.append(change_control_policy)
        mutations_operations.append(add_process_module)
        mutations_operations.append(remove_process_module)
        mutations_operations.append(move_process_module)
    if scenario_data.ReconfigurationEnum.TRANSPORT_CAPACITY in transformations:
        mutations_operations.append(add_transport_resource)
        mutations_operations.append(remove_transport_resource)
    if scenario_data.ReconfigurationEnum.LAYOUT in transformations:
        mutations_operations.append(move_machine)
    if scenario_data.ReconfigurationEnum.SEQUENCING_LOGIC in transformations:
        mutations_operations.append(change_control_policy)
    if scenario_data.ReconfigurationEnum.ROUTING_LOGIC in transformations:
        mutations_operations.append(change_routing_policy)
    return mutations_operations


def mutation(individual):
    mutation_operation = random.choice(get_mutation_operations(individual[0]))
    adapter_object = individual[0]
    if mutation_operation(adapter_object):
        individual[0].ID = str(uuid1())
    add_default_queues_to_resources(adapter_object)
    clean_out_breakdown_states_of_resources(adapter_object)
    adjust_process_capacities(adapter_object)

    return (individual,)


def add_machine(adapter_object: adapters.ProductionSystemAdapter) -> bool:
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
    possible_processes = get_possible_production_processes_IDs(adapter_object)
    if num_process_modules > len(possible_processes):
        num_process_modules = len(possible_processes)
    process_module_list = random.sample(possible_processes, num_process_modules)
    process_module_list = list(flatten(process_module_list))

    control_policy = random.choice(
        adapter_object.scenario_data.options.machine_controllers
    )
    possible_positions = deepcopy(adapter_object.scenario_data.options.positions)
    for resource in adapters.get_machines(adapter_object):
        if resource.location in possible_positions:
            possible_positions.remove(resource.location)
    if not possible_positions:
        return False
    location = random.choice(possible_positions)
    machine_ids = [
        resource.ID
        for resource in adapter_object.resource_data
        if isinstance(resource, resource_data.ProductionResourceData)
    ]
    machine_id = str(uuid1())
    adapter_object.resource_data.append(
        resource_data.ProductionResourceData(
            ID=machine_id,
            description="",
            capacity=1,
            location=location,
            controller=resource_data.ControllerEnum.PipelineController,
            control_policy=control_policy,
            process_ids=process_module_list,
        )
    )
    add_default_queues_to_resources(adapter_object)
    add_setup_states_to_machine(adapter_object, machine_id)
    return True


def add_setup_states_to_machine(
    adapter_object: adapters.ProductionSystemAdapter, machine_id: str
):
    machine = next(
        resource
        for resource in adapter_object.resource_data
        if resource.ID == machine_id
    )
    no_setup_state_ids = set(
        [
            state.ID
            for state in adapter_object.state_data
            if not isinstance(state, state_data.SetupStateData)
        ]
    )
    machine.state_ids = [
        state for state in machine.state_ids if state in no_setup_state_ids
    ]
    for state in adapter_object.state_data:
        if (
            not isinstance(state, state_data.SetupStateData)
            or state in machine.state_ids
        ):
            continue
        if (
            state.origin_setup in machine.process_ids
            or state.target_setup in machine.process_ids
        ):
            machine.state_ids.append(state.ID)


def add_transport_resource(adapter_object: adapters.ProductionSystemAdapter) -> bool:
    """
    Function that adds a random transport resource to the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if a transport resource was added, False otherwise (if adding is not possible due to constraint violations).
    """
    control_policy = random.choice(
        adapter_object.scenario_data.options.transport_controllers
    )

    transport_resource_ids = [
        resource.ID
        for resource in adapter_object.resource_data
        if isinstance(resource, resource_data.TransportResourceData)
    ]
    transport_resource_id = str(uuid1())
    possible_processes = get_possible_transport_processes_IDs(adapter_object)
    transport_process = random.choice(possible_processes)
    while transport_resource_id in transport_resource_ids:
        transport_resource_id = str(uuid1())
    adapter_object.resource_data.append(
        resource_data.TransportResourceData(
            ID=transport_resource_id,
            description="",
            capacity=1,
            location=(0.0, 0.0),
            controller="TransportController",
            control_policy=control_policy,
            process_ids=[transport_process],
        )
    )
    return True


def add_process_module(adapter_object: adapters.ProductionSystemAdapter) -> bool:
    """
    Function that adds a random process module to a random machine of the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if a process module was added, False otherwise (if adding is not possible due to constraint violations).
    """
    possible_machines = adapters.get_machines(adapter_object)
    if not possible_machines:
        return False
    possible_processes = get_possible_production_processes_IDs(adapter_object)
    machine = random.choice(possible_machines)
    process_module_to_add = random.sample(possible_processes, k=1)
    process_module_to_add = list(flatten(process_module_to_add))
    for process_id in process_module_to_add:
        if process_id not in machine.process_ids:
            machine.process_ids.append(process_id)
    add_setup_states_to_machine(adapter_object, machine.ID)
    return True


def remove_machine(adapter_object: adapters.ProductionSystemAdapter) -> bool:
    """
    Function that removes a random machine from the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if a machine was removed, False otherwise (if removing is not possible due to constraint violations).
    """
    possible_machines = adapters.get_machines(adapter_object)
    if not possible_machines:
        return False
    machine = random.choice(possible_machines)
    adapter_object.resource_data.remove(machine)
    return True


def remove_transport_resource(adapter_object: adapters.ProductionSystemAdapter) -> bool:
    """
    Function that removes a random transport resource from the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if a transport resource was removed, False otherwise (if removing is not possible due to constraint violations).
    """
    transport_resources = adapters.get_transport_resources(adapter_object)
    if not transport_resources:
        return False
    transport_resource = random.choice(transport_resources)
    adapter_object.resource_data.remove(transport_resource)
    return True


def remove_process_module(adapter_object: adapters.ProductionSystemAdapter) -> bool:
    """
    Function that removes a random process module from a random machine of the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if a process module was removed, False otherwise (if removing is not possible due to constraint violations).
    """
    possible_machines = adapters.get_machines(adapter_object)
    if not possible_machines:
        return False
    machine = random.choice(possible_machines)

    possible_processes = get_possible_production_processes_IDs(adapter_object)
    process_modules = get_grouped_processes_of_machine(machine, possible_processes)
    if not process_modules:
        return False
    process_module_to_delete = random.choice(process_modules)

    for process in process_module_to_delete:
        machine.process_ids.remove(process)
    add_setup_states_to_machine(adapter_object, machine.ID)
    return True


def move_process_module(adapter_object: adapters.ProductionSystemAdapter) -> bool:
    """
    Function that moves a random process module from a random machine to another random machine of the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if a process module was moved, False otherwise (if moving is not possible due to constraint violations).
    """
    possible_machines = adapters.get_machines(adapter_object)
    if not possible_machines or len(possible_machines) < 2:
        return False
    from_machine = random.choice(possible_machines)
    possible_machines.remove(from_machine)
    to_machine = random.choice(possible_machines)

    possible_processes = get_possible_production_processes_IDs(adapter_object)
    grouped_process_module_IDs = get_grouped_processes_of_machine(
        from_machine, possible_processes
    )
    if not grouped_process_module_IDs:
        return False
    process_module_to_move = random.choice(grouped_process_module_IDs)
    for process_module in process_module_to_move:
        from_machine.process_ids.remove(process_module)
        to_machine.process_ids.append(process_module)
    add_setup_states_to_machine(adapter_object, from_machine.ID)
    add_setup_states_to_machine(adapter_object, to_machine.ID)
    return True


def arrange_machines(adapter_object: adapters.ProductionSystemAdapter) -> None:
    possible_positions = deepcopy(adapter_object.scenario_data.options.positions)
    for machine in adapters.get_machines(adapter_object):
        machine.location = random.choice(possible_positions)
        possible_positions.remove(machine.location)


def move_machine(adapter_object: adapters.ProductionSystemAdapter) -> bool:
    """
    Function that moves a random machine to a random position of the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if a machine was moved, False otherwise (if moving is not possible due to constraint violations).
    """
    possible_machines = adapters.get_machines(adapter_object)
    if not possible_machines:
        return False
    moved_machine = random.choice(possible_machines)
    possible_positions = deepcopy(adapter_object.scenario_data.options.positions)
    for machine in possible_machines:
        if machine.location in possible_positions:
            possible_positions.remove(machine.location)
    if not possible_positions:
        return False
    moved_machine.location = random.choice(possible_positions)
    return True


def change_control_policy(adapter_object: adapters.ProductionSystemAdapter) -> bool:
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
    if isinstance(resource, resource_data.ProductionResourceData):
        possible_control_policies = deepcopy(
            adapter_object.scenario_data.options.machine_controllers
        )
    else:
        possible_control_policies = deepcopy(
            adapter_object.scenario_data.options.transport_controllers
        )
    
    if len(possible_control_policies) < 2:
        return False
    possible_control_policies.remove(resource.control_policy)
    new_control_policy = random.choice(possible_control_policies)
    resource.control_policy = new_control_policy
    return True


def change_routing_policy(adapter_object: adapters.ProductionSystemAdapter) -> None:
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


def get_grouped_processes_of_machine(
    machine: resource_data.ProductionResourceData,
    possible_processes: List[Union[str, Tuple[str, ...]]],
) -> List[Tuple[str]]:
    grouped_processes = []
    for group in possible_processes:
        if isinstance(group, str):
            group = tuple([group])
        for process in machine.process_ids:
            if process in group:
                grouped_processes.append(group)
                break
    return grouped_processes


def get_num_of_process_modules(
    adapter_object: adapters.ProductionSystemAdapter,
) -> Dict[Tuple[str], int]:
    possible_processes = get_possible_production_processes_IDs(adapter_object)
    num_of_process_modules = {}
    for process in possible_processes:
        if isinstance(process, str):
            process = tuple([process])
        num_of_process_modules[process] = 0
    for machine in adapters.get_machines(adapter_object):
        machine_processes = get_grouped_processes_of_machine(
            machine, possible_processes
        )
        for process in machine_processes:
            num_of_process_modules[process] += 1
    return num_of_process_modules


def get_reconfiguration_cost(
    adapter_object: adapters.ProductionSystemAdapter,
    baseline: adapters.ProductionSystemAdapter = None,
) -> float:
    num_machines = len(adapters.get_machines(adapter_object))
    num_transport_resources = len(adapters.get_transport_resources(adapter_object))
    num_process_modules = get_num_of_process_modules(adapter_object)
    if not baseline:
        num_machines_before = 4
        num_transport_resources_before = 1
        possible_processes = get_possible_production_processes_IDs(adapter_object)
        num_process_modules_before = {}
        for process in possible_processes:
            if isinstance(process, str):
                num_process_modules_before[tuple(process)] = 0
            else:
                num_process_modules_before[process] = 0
    else:
        num_machines_before = len(adapters.get_machines(baseline))
        num_transport_resources_before = len(adapters.get_transport_resources(baseline))
        num_process_modules_before = get_num_of_process_modules(baseline)

    machine_cost = max(
        0,
        (num_machines - num_machines_before)
        * adapter_object.scenario_data.info.machine_cost,
    )
    transport_resource_cost = max(
        0,
        (num_transport_resources - num_transport_resources_before)
        * adapter_object.scenario_data.info.transport_resource_cost,
    )
    process_module_cost = 0
    for process in num_process_modules:
        process_module_cost += max(
            0,
            (num_process_modules[process] - num_process_modules_before[process])
            * adapter_object.scenario_data.info.process_module_cost,
        )

    return machine_cost + transport_resource_cost + process_module_cost


def get_random_production_capacity(
    adapter_object: adapters.ProductionSystemAdapter,
) -> adapters.ProductionSystemAdapter:
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
    adapter_object.resource_data = adapters.get_transport_resources(adapter_object)
    for _ in range(num_machines):
        add_machine(adapter_object)

    return adapter_object


def get_random_transport_capacity(
    adapter_object: adapters.ProductionSystemAdapter,
) -> adapters.ProductionSystemAdapter:
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
    adapter_object.resource_data = adapters.get_machines(adapter_object)
    for _ in range(num_transport_resources):
        add_transport_resource(adapter_object)

    return adapter_object


def get_random_layout(
    adapter_object: adapters.ProductionSystemAdapter,
) -> adapters.ProductionSystemAdapter:
    """
    Function that randomly arranges the machines of the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        adapters.ProductionSystemAdapter: Production system configuration with specified scenario data and arranged machines.
    """
    possible_positions = deepcopy(adapter_object.scenario_data.options.positions)
    for machine in adapters.get_machines(adapter_object):
        machine.location = random.choice(possible_positions)
        possible_positions.remove(machine.location)
    return adapter_object


def get_random_control_policies(
    adapter_object: adapters.ProductionSystemAdapter,
) -> adapters.ProductionSystemAdapter:
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
    for machine in adapters.get_machines(adapter_object):
        machine.control_policy = random.choice(possible_production_control_policies)
    possible_transport_control_policies = deepcopy(
        adapter_object.scenario_data.options.transport_controllers
    )
    for transport_resource in adapters.get_transport_resources(adapter_object):
        transport_resource.control_policy = random.choice(
            possible_transport_control_policies
        )
    return adapter_object


def get_random_routing_logic(
    adapter_object: adapters.ProductionSystemAdapter,
) -> adapters.ProductionSystemAdapter:
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


def random_configuration_with_initial_solution(
    initial_adapters: List[adapters.ProductionSystemAdapter],
) -> adapters.ProductionSystemAdapter:
    """
    Function that creates a random configuration based on an list of initial solutions.

    Args:
        initial_adapters (List[adapters.ProductionSystemAdapter]): List of initial solutions.

    Returns:
        adapters.ProductionSystemAdapter: Random configuration based on an initial solution.
    """
    adapter_object = random.choice(initial_adapters)
    return random_configuration(adapter_object)


def adjust_process_capacities(
    adapter_object: adapters.ProductionSystemAdapter,
) -> adapters.ProductionSystemAdapter:
    """
    Function that adjusts the process capacities of the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        adapters.ProductionSystemAdapter: Production system configuration with adjusted process capacities.
    """
    for resource in adapter_object.resource_data:
        resource.process_capacities = [resource.capacity] * len(resource.process_ids)


def random_configuration(
    baseline: adapters.ProductionSystemAdapter,
) -> adapters.ProductionSystemAdapter:
    """
    Function that creates a random configuration based on a baseline configuration.

    Args:
        baseline (adapters.ProductionSystemAdapter): Baseline configuration.

    Returns:
        adapters.ProductionSystemAdapter: Random configuration based on a baseline configuration.
    """
    transformations = baseline.scenario_data.options.transformations
    invalid_configuration_counter = 0
    while True:
        adapter_object = baseline.model_copy(deep=True)
        adapter_object.ID = str(uuid1())

        if scenario_data.ReconfigurationEnum.PRODUCTION_CAPACITY in transformations:
            get_random_production_capacity(adapter_object)
        if scenario_data.ReconfigurationEnum.TRANSPORT_CAPACITY in transformations:
            get_random_transport_capacity(adapter_object)
        if (
            scenario_data.ReconfigurationEnum.LAYOUT in transformations
            and scenario_data.ReconfigurationEnum.PRODUCTION_CAPACITY
            not in transformations
        ):
            get_random_layout(adapter_object)
        if scenario_data.ReconfigurationEnum.SEQUENCING_LOGIC in transformations and (
            scenario_data.ReconfigurationEnum.PRODUCTION_CAPACITY not in transformations
            or scenario_data.ReconfigurationEnum.TRANSPORT_CAPACITY
            not in transformations
        ):
            get_random_control_policies(adapter_object)
        if scenario_data.ReconfigurationEnum.ROUTING_LOGIC in transformations:
            get_random_routing_logic(adapter_object)

        add_default_queues_to_resources(adapter_object)
        clean_out_breakdown_states_of_resources(adapter_object)
        adjust_process_capacities(adapter_object)
        if check_valid_configuration(adapter_object, baseline):
            break
        invalid_configuration_counter += 1
        if invalid_configuration_counter % 1000 == 0:
            logging.warning(f"More than {invalid_configuration_counter} invalid configurations were created in a row. Are you sure that the constraints are correct and not too strict?")
    return adapter_object


def valid_num_machines(configuration: adapters.ProductionSystemAdapter) -> bool:
    if (
        len(adapters.get_machines(configuration))
        > configuration.scenario_data.constraints.max_num_machines
    ):
        return False
    return True


def valid_transport_capacity(configuration: adapters.ProductionSystemAdapter) -> bool:
    if (
        len(adapters.get_transport_resources(configuration))
        > configuration.scenario_data.constraints.max_num_transport_resources
    ) or (len(adapters.get_transport_resources(configuration)) == 0):
        return False
    return True


def valid_num_process_modules(configuration: adapters.ProductionSystemAdapter) -> bool:
    for resource in configuration.resource_data:
        if (
            len(
                get_grouped_processes_of_machine(
                    resource, get_possible_production_processes_IDs(configuration)
                )
            )
            > configuration.scenario_data.constraints.max_num_processes_per_machine
        ):
            return False
    return True


def valid_positions(configuration: adapters.ProductionSystemAdapter) -> bool:
    try: 
        assert_no_redudant_locations(configuration)
    except ValueError as e:
        return False

    positions = [machine.location for machine in adapters.get_machines(configuration)]
    possible_positions = configuration.scenario_data.options.positions
    if any(position not in possible_positions for position in positions):
        return False
    return True


def valid_reconfiguration_cost(
    configuration: adapters.ProductionSystemAdapter,
    base_configuration: adapters.ProductionSystemAdapter,
) -> bool:
    reconfiguration_cost = get_reconfiguration_cost(
        adapter_object=configuration,
        baseline=base_configuration,
    )
    configuration.reconfiguration_cost = reconfiguration_cost

    if (
        reconfiguration_cost
        > configuration.scenario_data.constraints.max_reconfiguration_cost
    ):
        return False
    return True


def check_valid_configuration(
    configuration: adapters.ProductionSystemAdapter,
    base_configuration: adapters.ProductionSystemAdapter,
) -> bool:
    """
    Function that checks if a configuration is valid.

    Args:
        configuration (adapters.ProductionSystemAdapter): Configuration to be checked.
        base_configuration (adapters.ProductionSystemAdapter): Baseline configuration.

    Returns:
        bool: True if the configuration is valid, False otherwise.
    """
    if not valid_num_machines(configuration):
        return False
    if not valid_transport_capacity(configuration):
        return False
    if not valid_num_process_modules(configuration):
        return False
    try:
        assert_required_processes_in_resources_available(configuration)
    except ValueError as e:
        return False
    if not valid_positions(configuration):
        return False
    if not valid_reconfiguration_cost(configuration, base_configuration):
        return False
    return True


def get_throughput_time(pp: PostProcessor) -> float:
    throughput_time_for_products = pp.get_aggregated_throughput_time_data()
    if not throughput_time_for_products:
        throughput_time_for_products = [100000]
    avg_throughput_time = sum(throughput_time_for_products) / len(
        throughput_time_for_products
    )
    return avg_throughput_time


def get_wip(pp: PostProcessor) -> float:
    return sum(pp.get_aggregated_wip_data())


def get_throughput(pp: PostProcessor) -> float:
    return sum(pp.get_aggregated_throughput_data())


KPI_function_dict = {
    performance_indicators.KPIEnum.COST: get_reconfiguration_cost,
    performance_indicators.KPIEnum.TRHOUGHPUT_TIME: get_throughput_time,
    performance_indicators.KPIEnum.WIP: get_wip,
    performance_indicators.KPIEnum.THROUGHPUT: get_throughput,
}


def document_individual(
    solution_dict: Dict[str, Union[list, str]],
    save_folder: str,
    individual,
):
    adapter_object: adapters.ProductionSystemAdapter = individual[0]
    current_generation = solution_dict["current_generation"]

    if adapter_object.hash() not in solution_dict["hashes"]:
        solution_dict["hashes"][adapter_object.hash()] = {
            "generation": current_generation,
            "ID": adapter_object.ID,
        }

    adapters.JsonProductionSystemAdapter(**adapter_object.model_dump()).write_data(
        f"{save_folder}/generation_{current_generation}_{adapter_object.ID}.json"
    )


def evaluate(
    base_scenario: adapters.ProductionSystemAdapter,
    solution_dict: Dict[str, Union[list, str]],
    performances: dict,
    number_of_seeds: int,
    full_save_folder_file_path: str,
    individual,
) -> List[float]:
    """
    Function that evaluates a configuration.

    Args:
        base_scenario (adapters.ProductionSystemAdapter): Baseline configuration.
        solution_dict (Dict[str, Union[list, str]]): Dictionary containing the ids of existing solutions.
        performances (dict): Dictionary containing the performances of the current and previous generations.
        number_of_seeds (int): Number of seeds for the simulation runs.
        individual (List[adapters.ProductionSystemAdapter]): List if length 1 containing the configuration to be evaluated.

    Raises:
        ValueError: If the time range is not defined in the scenario data.

    Returns:
        List[float]: List of the fitness values of the configuration.
    """

    adapter_object: adapters.ProductionSystemAdapter = individual[0]
    adapter_object_hash = adapter_object.hash()
    if adapter_object_hash in solution_dict["hashes"]:
        evaluated_adapter_generation = solution_dict["hashes"][adapter_object_hash]["generation"]
        evaluated_adapter_id = solution_dict["hashes"][adapter_object_hash]["ID"]
        return performances[evaluated_adapter_generation][evaluated_adapter_id]["fitness"]

    if not check_valid_configuration(adapter_object, base_scenario):
        return [-100000 / weight for weight in get_weights(base_scenario, "max")]

    fitness_values = []

    for seed in range(number_of_seeds):
        runner_object = runner.Runner(adapter=adapter_object) 
        if not adapter_object.scenario_data.info.time_range:
            raise ValueError("time_range is not defined in scenario_data")
        adapter_object.seed = seed
        runner_object.initialize_simulation()
        runner_object.run(adapter_object.scenario_data.info.time_range)
        if full_save_folder_file_path:
            runner_object.save_results_as_csv(full_save_folder_file_path)
        df = runner_object.event_logger.get_data_as_dataframe()
        p = PostProcessor(df_raw=df)
        fitness = []
        for objective in adapter_object.scenario_data.objectives:
            if objective.name == performance_indicators.KPIEnum.COST:
                fitness.append(get_reconfiguration_cost(adapter_object, base_scenario))
                continue
            fitness.append(KPI_function_dict[objective.name](p))
        fitness_values.append(fitness)
    
    mean_fitness = [sum(fitness) / len(fitness) for fitness in zip(*fitness_values)]
    return mean_fitness
