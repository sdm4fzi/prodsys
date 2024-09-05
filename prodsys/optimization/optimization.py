from typing import Dict, List, Union
from prodsys import adapters, runner
from prodsys.adapters.adapter import assert_no_redudant_locations, assert_required_processes_in_resources_available, get_possible_production_processes_IDs
from prodsys.models import performance_indicators
from prodsys.optimization.util import get_grouped_processes_of_machine, get_num_of_process_modules, get_weights
from prodsys.util.post_processing import PostProcessor


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
    process_module_costs_dict = adapter_object.scenario_data.info.process_module_costs
    for process, current_module_count in num_process_modules.items():
        previous_module_count = num_process_modules_before.get(process, 0)
        process_str = process[0] if isinstance(process, tuple) else process
        if process_str in process_module_costs_dict:
            cost_per_module = process_module_costs_dict[process_str]
            process_module_cost += max(
                0,
                (current_module_count - previous_module_count) * cost_per_module
            )

    return machine_cost + transport_resource_cost + process_module_cost


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