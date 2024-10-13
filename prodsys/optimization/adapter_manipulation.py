from copy import deepcopy
import logging
from typing import Callable, List
from prodsys import adapters
from prodsys.adapters.adapter import add_default_queues_to_resources, get_possible_production_processes_IDs, get_possible_transport_processes_IDs, remove_queues_from_resources
from prodsys.models import resource_data, scenario_data
from prodsys.optimization.optimization import check_valid_configuration
from prodsys.optimization.util import add_setup_states_to_machine, adjust_process_capacities, clean_out_breakdown_states_of_resources, get_grouped_processes_of_machine, get_required_auxiliaries


import random
from uuid import uuid1

from prodsys.util.util import flatten


def crossover(ind1, ind2):
    ind1[0].ID = str(uuid1())
    ind2[0].ID = str(uuid1())

    crossover_type = random.choice(["machine", "partial_machine", "transport_resource"])
    adapter1: adapters.ProductionSystemAdapter = ind1[0]
    adapter2: adapters.ProductionSystemAdapter = ind2[0]
    machines_1 = adapters.get_machines(adapter1)
    machines_2 = adapters.get_machines(adapter2)
    remove_queues_from_resources(machines_1 + machines_2)
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
        if resource.input_location in possible_positions:
            possible_positions.remove(resource.input_location)
    if not possible_positions:
        return False
    input_location = random.choice(possible_positions)
    output_location = input_location
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
            input_location=input_location,
            output_location=output_location,
            controller=resource_data.ControllerEnum.PipelineController,
            control_policy=control_policy,
            process_ids=process_module_list,
        )
    )
    add_default_queues_to_resources(adapter_object)
    add_setup_states_to_machine(adapter_object, machine_id)
    return True


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
        if machine.input_location in possible_positions:
            possible_positions.remove(machine.input_location)
    if not possible_positions:
        return False
    new_input_location = random.choice(possible_positions)
    moved_machine.input_location = new_input_location
    moved_machine.output_location = new_input_location
    return True


def add_auxiliary(adapter_object: adapters.ProductionSystemAdapter) -> bool:
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
    queue = [queue for queue in adapter_object.queue_data if queue.ID == auxiliary.storages[storage_index]][0]
    if queue.capacity == auxiliary.quantity_in_storages[storage_index]:
        return False
    auxiliary.quantity_in_storages[storage_index] += 1
    return True

def remove_auxiliary(adapter_object: adapters.ProductionSystemAdapter) -> bool:
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
    if scenario_data.ReconfigurationEnum.AUXILIARY_CAPACITY in transformations:
        mutations_operations.append(add_auxiliary)
        mutations_operations.append(remove_auxiliary)
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


def arrange_machines(adapter_object: adapters.ProductionSystemAdapter) -> None:
    possible_positions = deepcopy(adapter_object.scenario_data.options.positions)
    for machine in adapters.get_machines(adapter_object):
        new_input_location = random.choice(possible_positions)
        machine.input_location = new_input_location
        machine.output_location = new_input_location
        possible_positions.remove(new_input_location)

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


def get_random_auxiliary_capacity(
    adapter_object: adapters.ProductionSystemAdapter,
) -> adapters.ProductionSystemAdapter:
    required_auxiliaries = get_required_auxiliaries(adapter_object)
    available_storage_capacities = {queue.ID: queue.capacity for queue in adapter_object.queue_data}
    for auxiliary in required_auxiliaries:
        for storage_index, storage in enumerate(auxiliary.storages):
            if available_storage_capacities[storage] == 0:
                continue
            random_capacity = random.choice(range(1, available_storage_capacities[storage] + 1))
            if available_storage_capacities[storage] - random_capacity < 0:
                random_capacity = available_storage_capacities[storage]
            auxiliary.quantity_in_storages[storage_index] = random_capacity
            available_storage_capacities[storage] -= random_capacity
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
        new_input_location = random.choice(possible_positions)
        machine.input_location = new_input_location
        machine.output_location = new_input_location
        possible_positions.remove(new_input_location)
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
        if scenario_data.ReconfigurationEnum.AUXILIARY_CAPACITY in transformations:
            get_random_auxiliary_capacity(adapter_object)
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