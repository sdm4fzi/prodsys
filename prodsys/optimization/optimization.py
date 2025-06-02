from typing import Dict, List, Optional, Tuple, Union
from prodsys import adapters, runner
from prodsys.models.production_system_data import (
    assert_no_redudant_locations,
    assert_required_processes_in_resources_available,
    get_possible_production_processes_IDs,
)
from prodsys.models import performance_indicators
from prodsys.optimization.optimization_data import (
    OptimizationResults,
    OptimizationSolutions,
)
from prodsys.optimization.util import (
    get_grouped_processes_of_machine,
    get_num_of_process_modules,
    get_required_auxiliaries,
    get_weights,
)
from prodsys.simulation import sim
from prodsys.simulation.runner import Runner
from prodsys.util.post_processing import PostProcessor


def get_process_module_cost(
    adapter_object: adapters.ProductionSystemData,
    num_process_modules: Dict[Tuple[str], int],
    num_process_modules_before: Dict[Tuple[str], int],
) -> float:
    num_process_modules = get_num_of_process_modules(adapter_object)

    sum_process_module_cost = 0
    process_module_cost = adapter_object.scenario_data.info.process_module_cost

    for process_tuple in num_process_modules:
        process = process_tuple[0]
        if isinstance(process_module_cost, dict):
            process_cost = process_module_cost.get(process, 0)
        else:
            process_cost = process_module_cost
        sum_process_module_cost += (
            num_process_modules[process_tuple]
            - num_process_modules_before.get(process_tuple, 0)
        ) * process_cost
    return sum_process_module_cost


def get_reconfiguration_cost(
    adapter_object: adapters.ProductionSystemData,
    baseline: adapters.ProductionSystemData = None,
) -> float:
    num_machines = len(adapters.get_production_resources(adapter_object))
    num_transport_resources = len(adapters.get_transport_resources(adapter_object))
    num_process_modules = get_num_of_process_modules(adapter_object)
    if not baseline:
        num_machines_before = 0
        num_transport_resources_before = 0
        possible_processes = get_possible_production_processes_IDs(adapter_object)
        num_process_modules_before = {}
        for process in possible_processes:
            if isinstance(process, str):
                num_process_modules_before[tuple(process)] = 0
            else:
                num_process_modules_before[process] = 0
    else:
        num_machines_before = len(adapters.get_production_resources(baseline))
        num_transport_resources_before = len(adapters.get_transport_resources(baseline))
        num_process_modules_before = get_num_of_process_modules(baseline)

    if adapter_object.depdendency_data:
        auxiliary_cost = get_auxiliary_cost(adapter_object, baseline)
    else:
        auxiliary_cost = 0

    machine_cost = (
        num_machines - num_machines_before
    ) * adapter_object.scenario_data.info.machine_cost
    transport_resource_cost = (
        num_transport_resources - num_transport_resources_before
    ) * adapter_object.scenario_data.info.transport_resource_cost
    process_module_cost = get_process_module_cost(
        adapter_object, num_process_modules, num_process_modules_before
    )
    if not adapter_object.scenario_data.info.selling_machines:
        machine_cost = max(0, machine_cost)
    if not adapter_object.scenario_data.info.selling_transport_resources:
        transport_resource_cost = max(0, transport_resource_cost)
    if not adapter_object.scenario_data.info.selling_process_modules:
        process_module_cost = max(0, process_module_cost)
    if not adapter_object.scenario_data.info.selling_auxiliaries:
        auxiliary_cost = max(0, auxiliary_cost)
    return machine_cost + transport_resource_cost + process_module_cost + auxiliary_cost


def get_auxiliary_cost(
    adapter_object: adapters.ProductionSystemData,
    baseline: adapters.ProductionSystemData,
) -> float:
    auxiliary_cost = 0
    for new_auxiliary, auxiliary_before in zip(
        adapter_object.depdendency_data, baseline.depdendency_data
    ):
        for i, storage in enumerate(new_auxiliary.quantity_in_storages):
            storage_before = auxiliary_before.quantity_in_storages[i]
            auxiliary_cost += max(
                0,
                (storage - storage_before)
                * adapter_object.scenario_data.info.auxiliary_cost,
            )
    return auxiliary_cost


def valid_num_machines(configuration: adapters.ProductionSystemData) -> bool:
    if (
        len(adapters.get_production_resources(configuration))
        > configuration.scenario_data.constraints.max_num_machines
    ):
        return False
    return True


def valid_transport_capacity(configuration: adapters.ProductionSystemData) -> bool:
    if (
        len(adapters.get_transport_resources(configuration))
        > configuration.scenario_data.constraints.max_num_transport_resources
    ) or (len(adapters.get_transport_resources(configuration)) == 0):
        return False
    return True


def valid_num_process_modules(configuration: adapters.ProductionSystemData) -> bool:
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


def valid_positions(configuration: adapters.ProductionSystemData) -> bool:
    try:
        assert_no_redudant_locations(configuration)
    except ValueError as e:
        return False

    positions = [
        machine.input_location
        for machine in adapters.get_production_resources(configuration)
    ]
    possible_positions = configuration.scenario_data.options.positions
    if any(position not in possible_positions for position in positions):
        return False
    return True


def valid_reconfiguration_cost(
    configuration: adapters.ProductionSystemData,
    base_configuration: adapters.ProductionSystemData,
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
    configuration: adapters.ProductionSystemData,
    base_configuration: adapters.ProductionSystemData,
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
        assert_required_auxiliaries_available(configuration)
    except ValueError as e:
        return False
    try:
        assert_required_processes_in_resources_available(configuration)
    except ValueError as e:
        return False
    if not valid_positions(configuration):
        # TODO: raise error if the positions cannot be changed (no production capacity or layout in transformations of scenario)
        return False
    if not valid_reconfiguration_cost(configuration, base_configuration):
        return False
    return True


def assert_required_auxiliaries_available(
    configuration: adapters.ProductionSystemData,
) -> bool:
    required_auxiliaries = get_required_auxiliaries(configuration)
    for auxiliary in required_auxiliaries:
        if not sum(auxiliary.quantity_in_storages) > 0:
            raise ValueError(f"Required auxiliary {auxiliary.ID} is not available.")


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


def evaluate_ea_wrapper(
    base_scenario: adapters.ProductionSystemData,
    solution_dict: Dict[str, Union[list, str]],
    number_of_seeds: int,
    full_save: bool,
    individual,
) -> tuple[list[float], dict]:
    return evaluate(
        base_scenario,
        solution_dict,
        number_of_seeds,
        individual[0],
        full_save=full_save,
    )


def evaluate(
    base_scenario: adapters.ProductionSystemData,
    solution_dict: OptimizationSolutions,
    number_of_seeds: int,
    adapter_object: adapters.ProductionSystemData,
    full_save: bool,
) -> tuple[Optional[list[float]], Optional[dict]]:
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
        tuple[list[float], dict]: The fitness values and the event log dict
    """
    sim.VERBOSE = 0
    adapter_object_hash = adapter_object.hash()
    if adapter_object_hash in solution_dict.hashes:
        return (
            None,
            None,
        )  # fitness and event log dict is obtained in optimizer from cache
    if not check_valid_configuration(adapter_object, base_scenario):
        return [-100000 / weight for weight in get_weights(base_scenario, "max")], None

    fitness_values = []

    for seed in range(number_of_seeds):
        runner_object = runner.Runner(production_system_data=adapter_object)
        if not adapter_object.scenario_data.info.time_range:
            raise ValueError("time_range is not defined in scenario_data")
        adapter_object.seed = seed
        runner_object.initialize_simulation()
        runner_object.run(adapter_object.scenario_data.info.time_range)
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
    # TODO: allow to return multiple runner objects in the future
    return mean_fitness, (
        runner_object.event_logger.get_data_as_dataframe().to_dict()
        if full_save
        else None
    )
