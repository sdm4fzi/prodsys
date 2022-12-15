import json
import random
from copy import copy, deepcopy
from typing import Dict, List, Union

from . import loader
from .sim import Environment
from .post_processing import PostProcessor


def crossover(ind1, ind2):
    crossover_type = random.choice(["machine", "partial_machine", "transport_resource"])
    if "machine " in crossover_type:
        machines_1_keys = ind1[0].get_machines()
        machines_2_keys = ind2[0].get_machines()
        if crossover_type == "partial_machine":
            min_length = max(len(machines_1_keys, machines_2_keys))
            machines_1_keys = machines_1_keys[:min_length]
            machines_2_keys = machines_2_keys[:min_length]

        machines_1_data = {
            key: data
            for key, data in ind1[0].resource_data.items()
            if key in machines_1_keys
        }
        machines_2_data = {
            key: data
            for key, data in ind2[0].resource_data.items()
            if key in machines_2_keys
        }

        for key in machines_1_keys:
            del ind1[0].resource_data[key]
        ind2[0].resource_data.update(machines_1_data)

        for key in machines_2_keys:
            del ind2[0].resource_data[key]
        ind1[0].resource_data.update(machines_2_data)

    if crossover_type == "transport_resource":
        tr1_keys = ind1[0].get_transport_resources()
        tr2_keys = ind2[0].get_transport_resources()

        tr1_data = {
            key: data for key, data in ind1[0].resource_data.items() if key in tr1_keys
        }
        tr2_data = {
            key: data for key, data in ind2[0].resource_data.items() if key in tr2_keys
        }

        for key in tr1_keys:
            del ind1[0].resource_data[key]
        ind2[0].resource_data.update(tr1_data)

        for key in tr2_keys:
            del ind2[0].resource_data[key]
        ind1[0].resource_data.update(tr2_data)

    ind1[0].add_default_queues(queue_capacity=100)
    ind2[0].add_default_queues(queue_capacity=100)

    return ind1, ind2


def mutation(scenario_dict, individual):
    mutation_operation = random.choice(
        [
            add_machine,
            add_transport_resource,
            add_process_module,
            remove_machine,
            remove_transport_resource,
            remove_process_module,
            move_machine,
            move_process_module,
            change_control_policy,
        ]
    )
    loader_object = individual[0]
    mutation_operation(loader_object, scenario_dict)
    individual[0].add_default_queues(queue_capacity=100)

    return (individual,)


def add_machine(loader_object: loader.CustomLoader, scenario_dict: dict) -> None:
    num_process_modules = (
        random.choice(
            range(scenario_dict["constraints"]["max_num_processes_per_machine"])
        )
        + 1
    )
    possible_processes = loader_object.get_processes()
    process_module_list = random.sample(possible_processes, num_process_modules)

    control_policy = random.choice(scenario_dict["options"]["machine_controllers"])
    possible_positions = deepcopy(scenario_dict["options"]["positions"])
    for machine_key in loader_object.get_machines():
        possible_positions.remove(loader_object.resource_data[machine_key]["location"])
    if possible_positions:
        location = random.choice(possible_positions)
        loader_object.add_machine(
            control_policy=control_policy,
            location=location,
            processes=process_module_list,
            states=["BS1"],
        )


def add_transport_resource(
    loader_object: loader.CustomLoader, scenario_dict: dict
) -> None:
    control_policy = random.choice(scenario_dict["options"]["transport_controllers"])
    loader_object.add_transport_resource(
        control_policy=control_policy,
        location=[0, 0],
        processes=["TP1"],
        states=["BS2"],
    )


def add_process_module(loader_object: loader.CustomLoader, scenario_dict: dict) -> None:
    possible_machines = loader_object.get_machines()
    if possible_machines:
        possible_processes = loader_object.get_processes()
        machine = random.choice(possible_machines)
        process_module_to_add = random.choice(possible_processes)
        loader_object.resource_data[machine]["processes"].append(process_module_to_add)


def remove_machine(loader_object: loader.CustomLoader, scenario_dict: dict) -> None:
    possible_machines = loader_object.get_machines()
    if possible_machines:
        machine = random.choice(possible_machines)
        del loader_object.resource_data[machine]


def remove_transport_resource(
    loader_object: loader.CustomLoader, scenario_dict: dict
) -> None:
    transport_resources = loader_object.get_transport_resources()
    if transport_resources:
        transport_resource = random.choice(transport_resources)
        del loader_object.resource_data[transport_resource]


def remove_process_module(
    loader_object: loader.CustomLoader, scenario_dict: dict
) -> None:
    possible_machines = loader_object.get_machines()
    if possible_machines:
        machine = random.choice(possible_machines)
        process_modules = loader_object.resource_data[machine]["processes"]
        if process_modules:
            process_module_to_delete = random.choice(process_modules)
            loader_object.resource_data[machine]["processes"].remove(
                process_module_to_delete
            )


def move_process_module(
    loader_object: loader.CustomLoader, scenario_dict: dict
) -> None:
    possible_machines = loader_object.get_machines()
    if possible_machines and len(possible_machines) > 1:
        from_machine = random.choice(possible_machines)
        possible_machines.remove(from_machine)
        to_machine = random.choice(possible_machines)
        process_modules = loader_object.resource_data[from_machine]["processes"]
        if process_modules:
            process_module_to_move = random.choice(process_modules)
            loader_object.resource_data[from_machine]["processes"].remove(
                process_module_to_move
            )
            loader_object.resource_data[to_machine]["processes"].append(
                process_module_to_move
            )


def move_machine(loader_object: loader.CustomLoader, scenario_dict: dict) -> None:
    possible_machines = loader_object.get_machines()
    if possible_machines:
        machine = random.choice(possible_machines)

        possible_positions = deepcopy(scenario_dict["options"]["positions"])
        for machine_key in loader_object.get_machines():
            possible_positions.remove(
                loader_object.resource_data[machine_key]["location"]
            )
        if possible_positions:
            loader_object.resource_data[machine]["location"] = random.choice(
                possible_positions
            )
        # else:
        #     remove_machine(loader_object, scenario_dict)


def change_control_policy(
    loader_object: loader.CustomLoader, scenario_dict: dict
) -> None:
    if loader_object.resource_data.keys():
        resource = random.choice(list(loader_object.resource_data.keys()))
        if resource in loader_object.get_machines():
            possible_control_policies = copy(
                scenario_dict["options"]["machine_controllers"]
            )
        else:
            possible_control_policies = copy(
                scenario_dict["options"]["transport_controllers"]
            )

        possible_control_policies.remove(
            loader_object.resource_data[resource]["control_policy"]
        )
        new_control_policy = random.choice(possible_control_policies)
        loader_object.resource_data[resource]["control_policy"] = new_control_policy


def calculate_reconfiguration_cost(
    scenario_dict: dict,
    configuration: loader.CustomLoader,
    baseline: loader.CustomLoader = None,
):
    num_machines = configuration.get_num_machines()
    num_transport_resources = configuration.get_num_transport_resources()
    num_process_modules = configuration.get_num_process_modules()
    if not baseline:
        num_machines_before = 4
        num_transport_resources_before = 1
        num_process_modules_before = {
            process: 0 for process in set(configuration.get_processes())
        }
    else:
        num_machines_before = baseline.get_num_machines()
        num_transport_resources_before = baseline.get_num_transport_resources()
        num_process_modules_before = baseline.get_num_process_modules()

    machine_cost = max(
        0, (num_machines - num_machines_before) * scenario_dict["costs"]["machine"]
    )
    transport_resource_cost = max(
        0,
        (num_transport_resources - num_transport_resources_before)
        * scenario_dict["costs"]["transport_resource"],
    )
    process_module_cost = 0
    possible_processes = baseline.get_processes()
    for process in set(possible_processes):
        if not process in num_process_modules.keys():
            num_process_modules[process] = 0
        process_module_cost += max(
            0,
            (num_process_modules[process] - num_process_modules_before[process])
            * scenario_dict["costs"]["process_module"],
        )

    return machine_cost + transport_resource_cost + process_module_cost


def random_configuration(
    scenario_dict: dict, base_scenario: str, reconfiguration=False
) -> loader.CustomLoader:

    loader_object = get_base_configuration(base_scenario)

    num_machines = (
        random.choice(range(scenario_dict["constraints"]["max_num_machines"])) + 1
    )
    num_transport_resources = (
        random.choice(
            range(scenario_dict["constraints"]["max_num_transport_resources"])
        )
        + 1
    )
    num_process_modules = [
        random.choice(
            range(scenario_dict["constraints"]["max_num_processes_per_machine"])
        )
        + 1
        for _ in range(num_machines)
    ]

    possible_processes = loader_object.get_processes()
    process_module_list = [
        random.sample(possible_processes, num_processes)
        for num_processes in num_process_modules
    ]

    loader_object.resource_data = {}
    loader_object.queue_data = {}

    possible_locations = deepcopy(scenario_dict["options"]["positions"])

    for machine_index, processes in enumerate(process_module_list):
        control_policy = random.choice(scenario_dict["options"]["machine_controllers"])
        location = random.choice(possible_locations)
        possible_locations.remove(location)

        loader_object.add_machine(
            control_policy=control_policy,
            location=location,
            processes=processes,
            states=["BS1"],
        )

    for transport_resource_index in range(num_transport_resources):
        control_policy = random.choice(
            scenario_dict["options"]["transport_controllers"]
        )
        loader_object.add_transport_resource(
            control_policy=control_policy,
            location=[0, 0],
            processes=["TP1"],
            states=["BS2"],
        )

    return loader_object


def check_valid_configuration(
    configuration: loader.CustomLoader,
    base_configuration: loader.CustomLoader,
    scenario_dict: dict,
) -> bool:
    if (
        configuration.get_num_machines()
        > scenario_dict["constraints"]["max_num_machines"]
    ):
        return False

    if (
        configuration.get_num_transport_resources()
        > scenario_dict["constraints"]["max_num_transport_resources"]
    ) or (configuration.get_num_transport_resources() == 0):
        return False

    for resource in configuration.resource_data.values():
        if (
            len(resource["processes"])
            > scenario_dict["constraints"]["max_num_processes_per_machine"]
        ):
            return False

    reconfiguration_cost = calculate_reconfiguration_cost(
        scenario_dict=scenario_dict,
        configuration=configuration,
        baseline=base_configuration,
    )
    configuration.reconfiguration_cost = reconfiguration_cost

    if reconfiguration_cost > scenario_dict["constraints"]["max_reconfiguration_cost"]:
        return False

    possibles_processes = set(base_configuration.get_processes())
    available_processes = configuration.get_num_process_modules().keys()

    if available_processes < possibles_processes:
        return False

    # TODO: add check with double positions!

    return True


def get_objective_values(environment: Environment, pp: PostProcessor) -> List[float]:
    reconfiguration_cost = environment.loader.reconfiguration_cost
    throughput_time = pp.get_aggregated_throughput_time_data()
    if not throughput_time:
        throughput_time = [100000]
    throughput = pp.get_aggregated_throughput_data()
    wip = pp.get_aggregated_wip_data()

    return [
        sum(throughput),
        sum(wip),
        reconfiguration_cost,
    ]


def get_base_configuration(filepath: str) -> loader.CustomLoader:
    loader_object = loader.CustomLoader()
    loader_object.read_data(filepath, "json")
    return loader_object


def evaluate(
    scenario_dict: dict,
    base_scenario: str,
    solution_dict: Dict[str, Union[list, str]],
    performances: dict,
    save_folder: str,
    individual,
) -> List[float]:
    loader_object: loader.CustomLoader = individual[0]
    current_generation = solution_dict["current_generation"]

    counter = len(performances[current_generation])
    performances[current_generation][str(counter)] = {}

    loader_object.to_json(f"{save_folder}/f_{current_generation}_{str(counter)}.json")

    for generation in solution_dict.keys():
        if (
            generation != "current_generation"
            and loader_object.to_dict() in solution_dict[generation]
        ):
            index = solution_dict[generation].index(loader_object.to_dict())
            return performances[generation][str(index)]["fitness"]

    solution_dict[current_generation].append(loader_object.to_dict())

    base_configuration = get_base_configuration(base_scenario)
    if not check_valid_configuration(loader_object, base_configuration, scenario_dict):
        return [-100000, 100000, 100000]

    e = Environment()
    e.loader = loader_object
    e.initialize_simulation()
    e.run(10000)

    df = e.data_collector.get_data()
    p = PostProcessor(df_raw=df)
    return get_objective_values(e, p)


if __name__ == "__main__":
    with open("data/scenario.json") as json_file:
        scenario_dict = json.load(json_file)
    loader_object = random_configuration(
        base_scenario="data/base_scenario.json", scenario_dict=scenario_dict
    )
    evaluate(loader_object)
