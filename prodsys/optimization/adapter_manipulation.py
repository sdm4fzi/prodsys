from __future__ import annotations

from calendar import prcal
from copy import deepcopy
import logging
from typing import Callable, List
from prodsys import adapters
from prodsys.models.production_system_data import (
    add_default_queues_to_resources,
    get_possible_production_processes_IDs,
    get_possible_transport_processes_IDs,
    remove_queues_from_resources,
)
from prodsys.models import resource_data, scenario_data
from prodsys.optimization.optimization import check_valid_configuration
from prodsys.optimization.util import (
    add_setup_states_to_machine,
    adjust_process_capacities,
    clean_out_breakdown_states_of_resources,
    get_grouped_processes_of_machine,
    get_required_auxiliaries,
)


import random
from uuid import uuid1

from prodsys.util.util import flatten


def crossover(ind1, ind2):
    ind1[0].ID = str(uuid1())
    ind2[0].ID = str(uuid1())

    crossover_type = random.choice(["machine", "partial_machine", "transport_resource"])
    adapter1: adapters.ProductionSystemData = ind1[0]
    adapter2: adapters.ProductionSystemData = ind2[0]
    machines_1 = adapters.get_production_resources(adapter1)
    machines_2 = adapters.get_production_resources(adapter2)
    remove_queues_from_resources(machines_1 + machines_2)
    transport_resources_1 = adapters.get_transport_resources(adapter1)
    transport_resources_2 = adapters.get_transport_resources(adapter2)
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

    add_default_queues_to_resources(adapter1)
    add_default_queues_to_resources(adapter2)
    clean_out_breakdown_states_of_resources(adapter1)
    clean_out_breakdown_states_of_resources(adapter2)
    adjust_process_capacities(adapter1)
    adjust_process_capacities(adapter2)

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
    possible_processes = get_possible_production_processes_IDs(adapter_object)
    if num_process_modules > len(possible_processes):
        num_process_modules = len(possible_processes)
    process_module_list = random.sample(possible_processes, num_process_modules)
    process_module_list = list(flatten(process_module_list))

    control_policy = random.choice(
        adapter_object.scenario_data.options.machine_controllers
    )
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
    add_default_queues_to_resources(adapter_object)
    add_setup_states_to_machine(adapter_object, machine_id)
    return True


def add_transport_resource(adapter_object: adapters.ProductionSystemData) -> bool:
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

    possible_processes = get_possible_transport_processes_IDs(adapter_object)
    transport_process = random.choice(possible_processes)

    transport_resource_id = f"resource_{uuid1().hex}"
    adapter_object.resource_data.append(
        resource_data.ResourceData(
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
    possible_processes = get_possible_production_processes_IDs(adapter_object)
    machine = random.choice(possible_machines)
    process_module_to_add = random.sample(possible_processes, k=1)
    process_module_to_add = list(flatten(process_module_to_add))
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
    possible_machines = adapters.get_production_resources(adapter_object)
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
    transport_resources = adapters.get_transport_resources(adapter_object)
    if not transport_resources:
        return False
    transport_resource = random.choice(transport_resources)
    adapter_object.resource_data.remove(transport_resource)
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

    possible_processes = get_possible_production_processes_IDs(adapter_object)
    process_modules = get_grouped_processes_of_machine(machine, possible_processes)
    if not process_modules:
        return False
    process_module_to_delete = random.choice(process_modules)

    for process in process_module_to_delete:
        machine.process_ids.remove(process)
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


def update_production_resource_location(
    resource: resource_data.ResourceData, new_location: List[float]
) -> None:
    """
    Function that updates the location of a machine.

    Args:
        resource (resource_data.ResourceData): Machine to update.
        location (List[float]): New location of the machine.
    """
    position_delta = [
        new_location[0] - resource.location[0],
        new_location[1] - resource.location[1],
    ]
    resource.location = new_location
    resource.input_location = [
        resource.input_location[0] + position_delta[0],
        resource.input_location[1] + position_delta[1],
    ]
    resource.output_location = [
        resource.output_location[0] + position_delta[0],
        resource.output_location[1] + position_delta[1],
    ]


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
    return True


def add_auxiliary(adapter_object: adapters.ProductionSystemData) -> bool:
    """
    Function that adds a random auxiliary component to the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if an auxiliary component was added, False otherwise (if adding is not possible due to constraint violations).
    """
    required_auxiliaries = get_required_auxiliaries(adapter_object)
    auxiliary = random.choice(required_auxiliaries)
    storage_index = random.choice(range(len(auxiliary.storages)))
    queue = [
        queue
        for queue in adapter_object.queue_data
        if queue.ID == auxiliary.storages[storage_index]
    ][0]
    if queue.capacity == auxiliary.quantity_in_storages[storage_index]:
        return False
    auxiliary.quantity_in_storages[storage_index] += 1
    return True


def remove_auxiliary(adapter_object: adapters.ProductionSystemData) -> bool:
    """
    Function that removes a random auxiliary component from the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if an auxiliary component was removed, False otherwise (if removing is not possible due to constraint violations).
    """
    required_auxiliaries = get_required_auxiliaries(adapter_object)
    auxiliary = random.choice(required_auxiliaries)
    storage_index = random.choice(range(len(auxiliary.storages)))
    if auxiliary.quantity_in_storages[storage_index] == 0:
        return False
    auxiliary.quantity_in_storages[storage_index] -= 1
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
    if isinstance(resource, resource_data.ResourceData):
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
    add_default_queues_to_resources(adapter_object)
    clean_out_breakdown_states_of_resources(adapter_object)
    adjust_process_capacities(adapter_object)

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
    adapter_object.resource_data = adapters.get_transport_resources(adapter_object)
    for _ in range(num_machines):
        add_machine(adapter_object)

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
    adapter_object.resource_data = adapters.get_production_resources(adapter_object)
    for _ in range(num_transport_resources):
        add_transport_resource(adapter_object)

    return adapter_object


def get_random_auxiliary_capacity(
    adapter_object: adapters.ProductionSystemData,
) -> adapters.ProductionSystemData:
    required_auxiliaries = get_required_auxiliaries(adapter_object)
    available_storage_capacities = {
        queue.ID: queue.capacity for queue in adapter_object.queue_data
    }
    for auxiliary in required_auxiliaries:
        for storage_index, storage in enumerate(auxiliary.storages):
            if available_storage_capacities[storage] == 0:
                continue
            random_capacity = random.choice(
                range(1, available_storage_capacities[storage] + 1)
            )
            if available_storage_capacities[storage] - random_capacity < 0:
                random_capacity = available_storage_capacities[storage]
            auxiliary.quantity_in_storages[storage_index] = random_capacity
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
    for machine in adapters.get_production_resources(adapter_object):
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
    if scenario_data.ReconfigurationEnum.AUXILIARY_CAPACITY in transformations:
        get_random_auxiliary_capacity(adapter_object)
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

    add_default_queues_to_resources(adapter_object)
    clean_out_breakdown_states_of_resources(adapter_object)
    adjust_process_capacities(adapter_object)
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
    transformations = baseline.scenario_data.options.transformations
    invalid_configuration_counter = 0
    while True:
        adapter_object = random_configuration(baseline)
        if adapter_object:
            return adapter_object
        invalid_configuration_counter += 1
        if invalid_configuration_counter % 1000 == 0:
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
            add_default_queues_to_resources(adapter_object)
            clean_out_breakdown_states_of_resources(adapter_object)
            adjust_process_capacities(adapter_object)

        # Update the adapter's ID to mark the change.
        adapter_object.ID = str(uuid1())

        # Fallback: if the manipulated configuration is not valid, generate a completely new one.
        if successful_mutations == num_manipulations and check_valid_configuration(
            adapter_object, baseline
        ):
            return adapter_object
        invalid_configuration_counter += 1
        if invalid_configuration_counter % 1000 == 0:
            logging.warning(
                f"More than {invalid_configuration_counter} invalid configurations were created in a row. Are you sure that the constraints are correct and not too strict?"
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
    scenario_data.ReconfigurationEnum.AUXILIARY_CAPACITY: [
        add_auxiliary,
        remove_auxiliary,
    ],
    scenario_data.ReconfigurationEnum.LAYOUT: [move_machine],
    scenario_data.ReconfigurationEnum.SETUP: [move_process_module],
    scenario_data.ReconfigurationEnum.SEQUENCING_LOGIC: [change_control_policy],
    scenario_data.ReconfigurationEnum.ROUTING_LOGIC: [change_routing_policy],
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
