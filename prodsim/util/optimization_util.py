import random
from copy import deepcopy
from typing import Dict, List, Union, Tuple, Literal, Callable
from enum import Enum

from uuid import uuid1
from collections.abc import Iterable
from pydantic import parse_obj_as

from prodsim import adapters, runner
from prodsim.util.post_processing import PostProcessor
from prodsim.data_structures import (
    resource_data,
    state_data,
    processes_data,
    performance_indicators,
    scenario_data
)

class BreakdownStateNamingConvention(str, Enum):
    MACHINE_BREAKDOWN_STATE = "BSM"
    TRANSPORT_RESOURCE_BREAKDOWN_STATE = "BST"
    PROCESS_MODULE_BREAKDOWN_STATE = "BSP"

def get_breakdown_state_ids_of_machine_with_processes(processes: List[str]) -> List[str]:
    state_ids = [
        BreakdownStateNamingConvention.MACHINE_BREAKDOWN_STATE
    ] + len(processes) * [
        BreakdownStateNamingConvention.PROCESS_MODULE_BREAKDOWN_STATE
    ]
    return state_ids

def clean_out_breakdown_states_of_resources(adapter_object: adapters.Adapter):
    for resource in adapter_object.resource_data:
        if isinstance(resource, resource_data.ProductionResourceData):
            resource.states = get_breakdown_state_ids_of_machine_with_processes(resource.processes)
        elif isinstance(resource, resource_data.TransportResourceData):
            resource.states = [BreakdownStateNamingConvention.TRANSPORT_RESOURCE_BREAKDOWN_STATE]
        else:
            raise ValueError("unknown type of resource for breakdown state handling")

def get_weights(adapter: adapters.Adapter, direction: Literal["min", "max"]) -> Tuple[float, ...]:
    weights = []
    if not adapter.scenario_data.weights:
        return tuple([1.0] * len(adapter.scenario_data.optimize))
    for kpi_name in adapter.scenario_data.optimize:
        weight = adapter.scenario_data.weights[kpi_name]
        kpi = parse_obj_as(performance_indicators.KPI_UNION, {"name": kpi_name})
        if kpi.target != direction:
            weight *= -1
        weights.append(weight)
    return tuple(weights)



def remove_queues_from_resource(
    machine: resource_data.ProductionResourceData, adapter: adapters.Adapter
) -> adapters.Adapter:
    if machine.input_queues or machine.output_queues:
        for queue_ID in machine.input_queues + machine.output_queues:
            for queue in adapter.queue_data:
                if queue.ID == queue_ID:
                    adapter.queue_data.remove(queue)
                    break
        for machine in adapters.get_machines(adapter):
            machine.input_queues = []
            machine.output_queues = []
        return adapter


def remove_unused_queues_from_adapter(adapter: adapters.Adapter) -> adapters.Adapter:
    for queue in adapter.queue_data:
        if not any(
            [
                queue.ID in machine.input_queues + machine.output_queues
                for machine in adapters.get_machines(adapter)
                if machine.input_queues or machine.output_queues
            ]
            + [queue.ID in source.output_queues for source in adapter.source_data]
            + [queue.ID in sink.input_queues for sink in adapter.sink_data]
        ):
            adapter.queue_data.remove(queue)
    return adapter


def add_default_queues_to_resources(
    adapter: adapters.Adapter, queue_capacity=0.0
) -> adapters.Adapter:
    for machine in adapters.get_machines(adapter):
        remove_queues_from_resource(machine, adapter)
        remove_unused_queues_from_adapter(adapter)
        input_queues, output_queues = adapters.get_default_queues_for_resource(
            machine, queue_capacity
        )
        machine.input_queues = list(adapters.get_set_of_IDs(input_queues))
        machine.output_queues = list(adapters.get_set_of_IDs(output_queues))
        adapter.queue_data += input_queues + output_queues
    return adapter


def crossover(ind1, ind2):
    ind1[0].ID = ""
    ind2[0].ID = ""

    crossover_type = random.choice(["machine", "partial_machine", "transport_resource"])
    adapter1: adapters.Adapter = ind1[0]
    adapter2: adapters.Adapter = ind2[0]
    machines_1 = adapters.get_machines(adapter1)
    machines_2 = adapters.get_machines(adapter2)
    transport_resources_1 = adapters.get_transport_resources(adapter1)
    transport_resources_2 = adapters.get_transport_resources(adapter2)
    if "machine " in crossover_type:
        adapter1.resource_data = transport_resources_1
        adapter2.resource_data = transport_resources_2
        if crossover_type == "partial_machine":
            min_length = max(len(machines_1, machines_2))
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

    return ind1, ind2

def get_mutation_operations(adapter_object: adapters.Adapter) -> List[Callable]:
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
    individual[0].ID = ""
    mutation_operation = random.choice(
        get_mutation_operations(individual[0])
    )
    adapter_object = individual[0]
    mutation_operation(adapter_object)
    add_default_queues_to_resources(individual[0])
    clean_out_breakdown_states_of_resources(adapter_object)

    return (individual,)


def get_possible_production_processes_IDs(
    adapter_object: adapters.Adapter,
) -> Union[List[str], List[Tuple[str, ...]]]:
    possible_processes = adapter_object.process_data
    if not any(
        process.type == processes_data.ProcessTypeEnum.CapabilityProcesses
        for process in possible_processes
    ):
        return [
            process.ID
            for process in possible_processes
            if isinstance(process, processes_data.ProductionProcessData)
        ]
    capability_processes = [
        process
        for process in possible_processes
        if isinstance(process, processes_data.CapabilityProcessData)
        and process.time_model_id is not None
    ]
    process_dict = {}
    for process in capability_processes:
        if not process.capability in process_dict.keys():
            process_dict[process.capability] = []
        process_dict[process.capability].append(process.ID)
    return [tuple(value) for value in process_dict.values()]


def flatten(xs):
    for x in xs:
        if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
            yield from flatten(x)
        else:
            yield x


def add_machine(adapter_object: adapters.Adapter) -> None:
    num_process_modules = (
        random.choice(
            range(adapter_object.scenario_data.constraints.max_num_processes_per_machine)
        )
        + 1
    )
    possible_processes = get_possible_production_processes_IDs(adapter_object)
    if num_process_modules > len(possible_processes):
        num_process_modules = len(possible_processes)
    process_module_list = random.sample(possible_processes, num_process_modules)
    process_module_list = list(flatten(process_module_list))

    control_policy = random.choice(adapter_object.scenario_data.options.machine_controllers)
    possible_positions = deepcopy(adapter_object.scenario_data.options.positions)
    for resource in adapters.get_machines(adapter_object):
        if resource.location != (0, 0):
            possible_positions.remove(resource.location)
    if not possible_positions:
        return None
    location = random.choice(possible_positions)
    machine_ids = [
        resource.ID
        for resource in adapter_object.resource_data
        if isinstance(resource, resource_data.ProductionResourceData)
    ]
    machine_id = str(uuid1())
    while machine_id in machine_ids:
        machine_id = str(uuid1())
    adapter_object.resource_data.append(
        resource_data.ProductionResourceData(
            ID=machine_id,
            description="",
            capacity=1,
            location=location,
            controller="SimpleController",
            control_policy=control_policy,
            processes=process_module_list,
        )
    )
    add_default_queues_to_resources(adapter_object)
    add_setup_states_to_machine(adapter_object, machine_id)


def add_setup_states_to_machine(
    adapter_object: adapters.Adapter, machine_id: str
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
    machine.states = [state for state in machine.states if state in no_setup_state_ids]
    for state in adapter_object.state_data:
        if not isinstance(state, state_data.SetupStateData) or state in machine.states:
            continue
        if (
            state.origin_setup in machine.processes
            or state.target_setup in machine.processes
        ):
            machine.states.append(state.ID)


def add_transport_resource(
    adapter_object: adapters.Adapter
) -> None:
    control_policy = random.choice(adapter_object.scenario_data.options.transport_controllers)

    transport_resource_ids = [
        resource.ID
        for resource in adapter_object.resource_data
        if isinstance(resource, resource_data.TransportResourceData)
    ]
    transport_resource_id = str(uuid1())
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
            processes=["TP1"],
        )
    )


def add_process_module(adapter_object: adapters.Adapter) -> None:
    possible_machines = adapters.get_machines(adapter_object)
    if not possible_machines:
        return
    possible_processes = get_possible_production_processes_IDs(adapter_object)
    machine = random.choice(possible_machines)
    process_module_to_add = random.choice(possible_processes)
    if isinstance(process_module_to_add, str):
        process_module_to_add = [process_module_to_add]
    if not [
        process for process in process_module_to_add if process in machine.processes
    ]:
        machine.processes += process_module_to_add
    add_setup_states_to_machine(adapter_object, machine.ID)


def remove_machine(adapter_object: adapters.Adapter) -> None:
    possible_machines = adapters.get_machines(adapter_object)
    if not possible_machines:
        return
    machine = random.choice(possible_machines)
    adapter_object.resource_data.remove(machine)


def remove_transport_resource(
    adapter_object: adapters.Adapter) -> None:
    transport_resources = adapters.get_transport_resources(adapter_object)
    if not transport_resources:
        return
    transport_resource = random.choice(transport_resources)
    adapter_object.resource_data.remove(transport_resource)


def get_processes_by_capabilities(
    check_processes: List[processes_data.PROCESS_DATA_UNION],
) -> Dict[str, List[str]]:
    processes_by_capability = {}
    for process in check_processes:
        if process.capability not in processes_by_capability:
            processes_by_capability[process.capability] = []
        processes_by_capability[process.capability].append(process.ID)
    return processes_by_capability


def remove_process_module(
    adapter_object: adapters.Adapter
) -> None:
    possible_machines = adapters.get_machines(adapter_object)
    if not possible_machines:
        return
    machine = random.choice(possible_machines)

    possible_processes = get_possible_production_processes_IDs(adapter_object)
    process_modules = get_grouped_processes_of_machine(machine, possible_processes)
    if not process_modules:
        return
    process_module_to_delete = random.choice(process_modules)

    for process in process_module_to_delete:
        machine.processes.remove(process)
    add_setup_states_to_machine(adapter_object, machine.ID)


def move_process_module(adapter_object: adapters.Adapter) -> None:
    possible_machines = adapters.get_machines(adapter_object)
    if not possible_machines or len(possible_machines) < 2:
        return
    from_machine = random.choice(possible_machines)
    possible_machines.remove(from_machine)
    to_machine = random.choice(possible_machines)

    possible_processes = get_possible_production_processes_IDs(adapter_object)
    grouped_process_module_IDs = get_grouped_processes_of_machine(
        from_machine, possible_processes
    )
    if not grouped_process_module_IDs:
        return
    process_module_to_move = random.choice(grouped_process_module_IDs)
    for process_module in process_module_to_move:
        from_machine.processes.remove(process_module)
        to_machine.processes.append(process_module)
    add_setup_states_to_machine(adapter_object, from_machine.ID)
    add_setup_states_to_machine(adapter_object, to_machine.ID)


def arrange_machines(adapter_object: adapters.Adapter) -> None:
    possible_positions = deepcopy(adapter_object.scenario_data.options.positions)
    for machine in adapters.get_machines(adapter_object):
        machine.location = random.choice(possible_positions)
        possible_positions.remove(machine.location)


def move_machine(adapter_object: adapters.Adapter) -> None:
    possible_machines = adapters.get_machines(adapter_object)
    if not possible_machines:
        return
    machine = random.choice(possible_machines)
    possible_positions = deepcopy(adapter_object.scenario_data.options.positions)
    for machine in adapter_object.resource_data:
        if machine.location in possible_positions:
            possible_positions.remove(machine.location)
    if possible_positions:
        machine.location = random.choice(possible_positions)


def change_control_policy(
    adapter_object: adapters.Adapter
) -> None:
    if not adapter_object.resource_data:
        return
    resource = random.choice(adapter_object.resource_data)
    if isinstance(resource, resource_data.ProductionResourceData):
        possible_control_policies = deepcopy(adapter_object.scenario_data.options.machine_controllers)
    else:
        possible_control_policies = deepcopy(adapter_object.scenario_data.options.transport_controllers)

    possible_control_policies.remove(resource.control_policy)
    new_control_policy = random.choice(possible_control_policies)
    resource.control_policy = new_control_policy


def change_routing_policy(
    adapter_object: adapters.Adapter
) -> None:
    source = random.choice(adapter_object.source_data)
    possible_routing_policies = deepcopy(adapter_object.scenario_data.options.routing_heuristics)

    possible_routing_policies.remove(source.routing_heuristic)
    source.routing_heuristic = random.choice(possible_routing_policies)


def get_grouped_processes_of_machine(
    machine: resource_data.ProductionResourceData, possible_processes: Union[List[str], List[Tuple[str, ...]]]
) -> List[Tuple[str]]:
    if isinstance(possible_processes[0], str):
        return [tuple([process]) for process in machine.processes]
    grouped_processes = []
    for group in possible_processes:
        for process in machine.processes:
            if process in group:
                grouped_processes.append(group)
                break
    return grouped_processes


def get_num_of_process_modules(
    adapter_object: adapters.Adapter,
) -> Dict[Union[str, Tuple[str]], int]:
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
    adapter_object: adapters.Adapter,
    baseline: adapters.Adapter = None,
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
                num_process_modules_before[process] = 0
            else:
                num_process_modules_before[tuple(process)] = 0
    else:
        num_machines_before = len(adapters.get_machines(baseline))
        num_transport_resources_before = len(adapters.get_transport_resources(baseline))
        num_process_modules_before = get_num_of_process_modules(baseline)

    machine_cost = max(
        0, (num_machines - num_machines_before) * adapter_object.scenario_data.info.machine_cost
    )
    transport_resource_cost = max(
        0,
        (num_transport_resources - num_transport_resources_before)
        * adapter_object.scenario_data.info.transport_resource_cost,
    )
    process_module_cost = 0
    for process in num_process_modules:
        if not process in num_process_modules.keys():
            continue
        process_module_cost += max(
            0,
            (num_process_modules[process] - num_process_modules_before[process])
            * adapter_object.scenario_data.info.process_module_cost,
        )

    return machine_cost + transport_resource_cost + process_module_cost


def get_random_production_capacity(
    adapter_object: adapters.Adapter,
) -> adapters.Adapter:
    num_machines = (
            random.choice(range(adapter_object.scenario_data.constraints.max_num_machines)) + 1
        )
    adapter_object.resource_data = adapters.get_transport_resources(adapter_object)
    for _ in range(num_machines):
        add_machine(adapter_object)

    return adapter_object


def get_random_transport_capacity(
    adapter_object: adapters.Adapter,
) -> adapters.Adapter:
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
    adapter_object: adapters.Adapter,
) -> adapters.Adapter:
    possible_positions = deepcopy(adapter_object.scenario_data.options.positions)
    for machine in adapters.get_machines(adapter_object):
        machine.location = random.choice(possible_positions)
        possible_positions.remove(machine.location)
    return adapter_object

def get_random_control_policies(
    adapter_object: adapters.Adapter,
) -> adapters.Adapter:
    possible_production_control_policies = deepcopy(adapter_object.scenario_data.options.machine_controllers)
    for machine in adapters.get_machines(adapter_object):
        machine.control_policy = random.choice(possible_production_control_policies)
    possible_transport_control_policies = deepcopy(adapter_object.scenario_data.options.transport_controllers)
    for transport_resource in adapters.get_transport_resources(adapter_object):
        transport_resource.control_policy = random.choice(possible_transport_control_policies)
    return adapter_object

def get_random_routing_logic(
    adapter_object: adapters.Adapter,
) -> adapters.Adapter:
    possible_routing_logics = deepcopy(adapter_object.scenario_data.options.routing_heuristics)
    for source in adapter_object.source_data:
        source.routing_heuristic = random.choice(possible_routing_logics)
    return adapter_object

def random_configuration(baseline: adapters.Adapter
) -> adapters.Adapter:
    while True:
        adapter_object = baseline.copy(deep=True)
        get_random_production_capacity(adapter_object)
        get_random_transport_capacity(adapter_object)
        get_random_routing_logic(adapter_object)
        add_default_queues_to_resources(adapter_object)
        clean_out_breakdown_states_of_resources(adapter_object)
        if check_valid_configuration(adapter_object, baseline):
            break

    return adapter_object

def partial_random_configuration(baseline: adapters.Adapter
) -> adapters.Adapter:
    transformations = baseline.scenario_data.options.transformations
    while True:
        adapter_object = baseline.copy(deep=True)
        if scenario_data.ReconfigurationEnum.PRODUCTION_CAPACITY in transformations:
            get_random_production_capacity(adapter_object)
        if scenario_data.ReconfigurationEnum.TRANSPORT_CAPACITY in transformations:
            get_random_transport_capacity(adapter_object)
        if scenario_data.ReconfigurationEnum.LAYOUT in transformations:
            get_random_layout(adapter_object)
        if scenario_data.ReconfigurationEnum.SEQUENCING_LOGIC in transformations:
            get_random_control_policies(adapter_object)
        if scenario_data.ReconfigurationEnum.ROUTING_LOGIC in transformations:
            get_random_routing_logic(adapter_object)

        add_default_queues_to_resources(adapter_object)
        clean_out_breakdown_states_of_resources(adapter_object)
        if check_valid_configuration(adapter_object, baseline):
            break        

    return adapter_object


def check_valid_configuration(
    configuration: adapters.Adapter,
    base_configuration: adapters.Adapter,
) -> bool:
    if (
        len(adapters.get_machines(configuration))
        > configuration.scenario_data.constraints.max_num_machines
    ):
        return False

    if (
        len(adapters.get_transport_resources(configuration))
        > configuration.scenario_data.constraints.max_num_transport_resources
    ) or (len(adapters.get_transport_resources(configuration)) == 0):
        return False

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

    if set(
        flatten(
            [resource.processes for resource in adapters.get_machines(configuration)]
        )
    ) < set(flatten(get_possible_production_processes_IDs(configuration))):
        return False

    reconfiguration_cost = get_reconfiguration_cost(
        adapter_object=configuration,
        baseline=base_configuration,
    )
    configuration.reconfiguration_cost = reconfiguration_cost

    if reconfiguration_cost > configuration.scenario_data.constraints.max_reconfiguration_cost:
        return False

    return True


def get_throughput_time(pp: PostProcessor) -> float:
    throughput_time_for_materials = pp.get_aggregated_throughput_time_data()
    if not throughput_time_for_materials:
        throughput_time_for_materials = [100000]
    avg_throughput_time = sum(throughput_time_for_materials) / len(
        throughput_time_for_materials
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
    adapter_object: adapters.Adapter = individual[0]
    current_generation = solution_dict["current_generation"]

    if not adapter_object.ID:
        adapter_object.ID = str(uuid1())
        solution_dict[current_generation].append(adapter_object.ID)

    adapters.JsonAdapter(**adapter_object.dict()).write_data(
        f"{save_folder}/f_{current_generation}_{adapter_object.ID}.json"
    )


def evaluate(
    base_scenario: adapters.Adapter,
    solution_dict: Dict[str, Union[list, str]],
    performances: dict,
    individual,
) -> List[float]:

    adapter_object: adapters.Adapter = individual[0]
    current_generation = solution_dict["current_generation"]

    if adapter_object.ID:
        for generation in solution_dict.keys():
            if (
                generation != "current_generation"
                and not generation == current_generation
                and adapter_object.ID in solution_dict[generation]
            ):
                print("solution from generation ", generation,"with name:", adapter_object.ID)
                return performances[generation][adapter_object.ID]["fitness"]

    if not check_valid_configuration(adapter_object, base_scenario):
        print("invalid configuration")
        return [-100000 * weight for weight in get_weights(base_scenario, "max")]

    runner_object = runner.Runner(adapter=adapter_object)
    runner_object.initialize_simulation()
    if not adapter_object.scenario_data.info.time_range:
        raise ValueError("time_range is not defined in scenario_data")
    runner_object.run(adapter_object.scenario_data.info.time_range)
    df = runner_object.data_collector.get_data_as_dataframe()
    p = PostProcessor(df_raw=df)

    fitness = []
    for kpi_name in adapter_object.scenario_data.optimize:
        if kpi_name == performance_indicators.KPIEnum.COST:
            fitness.append(
                get_reconfiguration_cost(adapter_object, base_scenario)
            )
            continue
        fitness.append(KPI_function_dict[kpi_name](p))

    return fitness
