from dataclasses import dataclass
import json
from typing import List
from env import Environment
import loader
import print_util
from post_processing import PostProcessor

import random


def evaluate(options_dict, dict_results):
    # Do Simulation runs of all options and return dict_results
    pass

def crossover(ind1, ind2):
    return ind1, ind2



def mutation(individual):
    return individual,


def initPopulation(options_dict, pcls, ind_init):
    # Generate initial population without evaluation ->
    pass


def calculate_reconfiguration_cost(scenario_dict: dict, num_machines: int, num_transport_resources: int, process_modules: List[List[str]], baseline: loader.CustomLoader=None):
    if not baseline:
        num_machines_before = 4
        num_transport_resources_before = 1
        num_process_modules_before = {process: 0 for process in set(process_module_list)}
    else:
        num_machines_before = baseline.get_num_machines()
        num_transport_resources_before = baseline.get_num_transport_resources()
        num_process_modules_before = baseline.get_num_process_modules()

    print("machines", num_machines, num_machines_before)
    print("transport_resources", num_transport_resources, num_transport_resources_before)

    machine_cost = max(0, (num_machines - num_machines_before) * scenario_dict["costs"]["machine"])
    transport_resource_cost = max(0, (num_transport_resources - num_transport_resources_before) * scenario_dict["costs"]["transport_resource"])
    process_module_cost = 0
    process_module_list = [item for sublist in process_modules for item in sublist]
    for process in set(process_module_list):
        print(process, process_module_list.count(process), num_process_modules_before[process])
        process_module_cost += max(0, (process_module_list.count(process) - num_process_modules_before[process]) * scenario_dict["costs"]["process_module"])

    return machine_cost + transport_resource_cost + process_module_cost        


def random_configuration(base_scenario: str, scenario_dict: dict, reconfiguration=False):

    loader_object = loader.CustomLoader()
    loader_object.read_data(base_scenario, "json")

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
    process_module_list = [random.sample(possible_processes, num_processes) for num_processes in num_process_modules]

    reconfiguration_cost = calculate_reconfiguration_cost(scenario_dict=scenario_dict, num_machines=num_machines, num_transport_resources=num_transport_resources, process_modules=process_module_list, baseline=loader_object)
    valid_configuration = True

    if reconfiguration_cost > scenario_dict["constraints"]["max_reconfiguration_cost"]:
        valid_configuration = False  

    available_processes = set([item for sublist in process_module_list for item in sublist])
    print(process_module_list)
    print(available_processes, possible_processes)

    if available_processes < set(possible_processes):
        valid_configuration = False
    loader_object.valid_configuration = valid_configuration
    capacity = 100

    loader_object.resource_data = {}
    loader_object.queue_data = {}


    for machine_index, processes in enumerate(process_module_list):
        control_policy = random.choice(scenario_dict["options"]["machine_controllers"])
        location = random.choice(scenario_dict["options"]["positions"])

        loader_object.add_resource_with_default_queue(
            ID="M" + str(machine_index),
            description="Machine " + str(machine_index),
            controller="SimpleController",
            control_policy=control_policy,
            location=location,
            capacity=1,
            processes=processes,
            states="BS1",
            queue_capacity=capacity,
        )

    for transport_resource_index in range(num_transport_resources):
        control_policy = random.choice(scenario_dict["options"]["transport_controllers"])
        loader_object.add_resource(
            ID="TR" + str(transport_resource_index),
            description="Transport resource " + str(transport_resource_index),
            controller="TransportController",
            control_policy=control_policy,
            location=[0,0],
            capacity=1,
            processes=["TP1"],
            states="BS2"
        )

    return loader_object

def evaluate(individual):
    loader_object: loader.CustomLoader = individual[0]
    if not loader_object.valid_configuration:
        return [100000 for _ in range(2)]
    e = Environment()
    e.loader = loader_object
    e.initialize_simulation()

    import time

    t_0 = time.perf_counter()

    e.run(4000)

    t_1 = time.perf_counter()

    print_util.print_simulation_info(e, t_0, t_1)    

    e.data_collector.log_data_to_csv(filepath="data/data21.csv")


    p = PostProcessor(filepath="data/data21.csv")
    p.print_aggregated_data()
    return list(p.get_ea_data()) + [1]
    

if __name__ == '__main__':
    with open('data/scenario.json') as json_file:
        scenario_dict = json.load(json_file)
    loader_object = random_configuration(base_scenario='data/base_scenario.json', scenario_dict=scenario_dict)
    evaluate(loader_object)
    
