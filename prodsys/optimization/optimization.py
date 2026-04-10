from enum import Enum
from typing import Dict, List, Literal, Optional, Tuple, Union
import logging
import math
from prodsys import adapters, runner
from prodsys.models.production_system_data import (
    assert_no_redundant_locations,
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
    get_required_primitives,
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
    num_transport_resources = len(adapters.get_transport_resources(adapter_object)) #TODO: add more complex cost calculation for conveyors/can_move=False: calculate based on costs per meter or cost per link
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

    if adapter_object.dependency_data:
        primitive_cost = get_primitive_cost(adapter_object, baseline)
    else:
        primitive_cost = 0

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
    if not adapter_object.scenario_data.info.selling_primitives:
        primitive_cost = max(0, primitive_cost)
    return machine_cost + transport_resource_cost + process_module_cost + primitive_cost


def get_primitive_cost(
    adapter_object: adapters.ProductionSystemData,
    baseline: adapters.ProductionSystemData,
) -> float:
    primitive_cost = 0
    for new_primitive, before_primitive in zip(
        adapter_object.primitive_data, baseline.primitive_data
    ):
        for i, storage in enumerate(new_primitive.quantity_in_storages):
            storage_before = before_primitive.quantity_in_storages[i]
            primitive_cost += max(
                0,
                (storage - storage_before)
                * adapter_object.scenario_data.info.primitive_cost,
            )
    return primitive_cost


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
        assert_no_redundant_locations(configuration)
    except ValueError as e:
        return False

    positions = [
        machine.location
        for machine in adapters.get_production_resources(configuration)
    ]
    possible_positions = configuration.scenario_data.options.positions
    # If no positions are specified, any position is valid
    if possible_positions and any(position not in possible_positions for position in positions):
        return False
    return True


def resolve_process_overload(
    configuration: adapters.ProductionSystemData,
) -> None:
    """
    Resolves process-per-machine constraint violations in the base configuration by removing
    excess process groups from machines that exceed ``max_num_processes_per_machine``.

    Groups are removed in order (last-assigned groups are dropped first), and
    ``process_capacities`` is trimmed to stay in sync with ``process_ids``.

    Args:
        configuration (adapters.ProductionSystemData): Base configuration to fix in-place.
    """
    constraints = configuration.scenario_data.constraints
    max_per_machine = constraints.max_num_processes_per_machine
    possible_processes = get_possible_production_processes_IDs(configuration)

    for resource in configuration.resource_data:
        grouped = get_grouped_processes_of_machine(resource, possible_processes)
        if len(grouped) <= max_per_machine:
            continue

        groups_to_keep = set(map(tuple, grouped[:max_per_machine]))
        groups_to_remove = [g for g in grouped[max_per_machine:]]
        ids_to_remove = {pid for group in groups_to_remove for pid in group}

        old_count = len(resource.process_ids)
        resource.process_ids = [pid for pid in resource.process_ids if pid not in ids_to_remove]
        new_count = len(resource.process_ids)

        if resource.process_capacities and len(resource.process_capacities) > new_count:
            resource.process_capacities = resource.process_capacities[:new_count]

        removed_groups = [list(g) for g in groups_to_remove]
        logging.warning(
            f"[resolve_process_overload] Machine '{resource.ID}': removed {old_count - new_count} "
            f"process ID(s) from {old_count} to {new_count} to satisfy "
            f"max_num_processes_per_machine={max_per_machine}. "
            f"Dropped groups: {removed_groups}"
        )


def resolve_invalid_positions(
    configuration: adapters.ProductionSystemData,
) -> None:
    """
    Resolves position constraint violations in the base configuration by snapping each
    machine that sits outside ``scenario_data.options.positions`` to the nearest available
    valid position (Euclidean distance). Co-located ports are updated to match.

    Machines already at a valid position keep their location; machines with invalid
    positions are processed in ascending order of their distance to the nearest free
    valid position so that closer machines get first pick.

    Args:
        configuration (adapters.ProductionSystemData): Base configuration to fix in-place.
    """
    possible_positions = configuration.scenario_data.options.positions
    if not possible_positions:
        return

    production_resources = adapters.get_production_resources(configuration)
    possible_set = {tuple(p) for p in possible_positions}

    taken: set[tuple] = {
        tuple(r.location)
        for r in production_resources
        if tuple(r.location) in possible_set
    }

    def _dist(a: list, b: list) -> float:
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

    invalid_resources = [r for r in production_resources if tuple(r.location) not in possible_set]

    # Sort so the machine closest to any valid position gets first pick
    invalid_resources.sort(
        key=lambda r: min(_dist(r.location, p) for p in possible_positions)
    )

    for resource in invalid_resources:
        old_location = list(resource.location)
        available = [p for p in possible_positions if tuple(p) not in taken]
        if not available:
            logging.warning(
                f"[resolve_invalid_positions] Machine '{resource.ID}': no free valid position "
                f"remaining — skipping (current location {old_location} stays invalid)."
            )
            continue

        nearest = min(available, key=lambda p: _dist(old_location, p))
        resource.location = list(nearest)
        taken.add(tuple(nearest))

        for port in configuration.port_data:
            if port.location == old_location:
                port.location = list(nearest)

        logging.warning(
            f"[resolve_invalid_positions] Machine '{resource.ID}': moved from {old_location} "
            f"to {list(nearest)} (nearest free valid position, distance "
            f"{_dist(old_location, nearest):.2f})."
        )


BaseValidationMode = Literal["strict", "loose", "none"]


def validate_base_configuration(
    configuration: adapters.ProductionSystemData,
    mode: BaseValidationMode = "strict",
) -> None:
    """
    Validates the base configuration for known start-up constraint violations and
    optionally auto-resolves them.

    Two classes of issues are checked:

    * **Process overload** — one or more machines have more process groups assigned than
      ``scenario_data.constraints.max_num_processes_per_machine`` allows.
    * **Invalid positions** — one or more machines sit outside the set of positions listed
      in ``scenario_data.options.positions``.

    Args:
        configuration (adapters.ProductionSystemData): Base configuration to validate.
        mode (BaseValidationMode): How to handle discovered violations:

            * ``"strict"`` *(default)* — raise a ``ValueError`` describing every violation.
              Nothing is modified.
            * ``"loose"`` — log a ``WARNING`` for every violation and auto-resolve it in-place
              via :func:`resolve_process_overload` and :func:`resolve_invalid_positions`.
            * ``"none"`` — skip validation entirely (same as not calling this function).

    Raises:
        ValueError: In ``"strict"`` mode when any violation is found.
    """
    if mode == "none":
        return

    constraints = configuration.scenario_data.constraints
    possible_processes = get_possible_production_processes_IDs(configuration)
    issues: List[str] = []

    # --- process overload ---
    overloaded = {}
    for resource in configuration.resource_data:
        grouped = get_grouped_processes_of_machine(resource, possible_processes)
        if len(grouped) > constraints.max_num_processes_per_machine:
            overloaded[resource.ID] = len(grouped)

    if overloaded:
        issues.append(
            f"Machines exceed max_num_processes_per_machine={constraints.max_num_processes_per_machine}: "
            f"{overloaded}. "
            f"In 'loose' mode excess groups are trimmed automatically (last-added groups first)."
        )

    # --- invalid positions ---
    possible_positions = configuration.scenario_data.options.positions
    if possible_positions:
        possible_set = {tuple(p) for p in possible_positions}
        production_resources = adapters.get_production_resources(configuration)
        invalid_pos = {
            r.ID: r.location
            for r in production_resources
            if tuple(r.location) not in possible_set
        }
        if invalid_pos:
            issues.append(
                f"Machines at positions not in scenario allowed positions: {invalid_pos}. "
                f"In 'loose' mode each machine is snapped to the nearest free valid position."
            )

    if not issues:
        return

    if mode == "strict":
        raise ValueError(
            "Base configuration has constraint violations — cannot start optimization.\n"
            + "\n".join(f"  • {issue}" for issue in issues)
        )

    # mode == "loose": warn and auto-fix
    for issue in issues:
        logging.warning(f"[validate_base_configuration] {issue}")

    if overloaded:
        resolve_process_overload(configuration)
    if possible_positions and invalid_pos:
        resolve_invalid_positions(configuration)


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
    verbose: bool = False,
) -> Tuple[bool, List[str]]:
    """
    Function that checks if a configuration is valid. All constraints are
    evaluated so that the returned list contains every violated constraint,
    not just the first one.

    Args:
        configuration (adapters.ProductionSystemAdapter): Configuration to be checked.
        base_configuration (adapters.ProductionSystemAdapter): Baseline configuration.
        verbose (bool): If True, use warning-level logging instead of debug-level.

    Returns:
        Tuple[bool, List[str]]: (True, []) if valid, or (False, [reason, ...]) listing every violated constraint.
    """
    log_func = logging.warning if verbose else logging.debug
    constraints = configuration.scenario_data.constraints
    reasons: List[str] = []

    num_production = len(adapters.get_production_resources(configuration))
    if num_production > constraints.max_num_machines:
        reasons.append(f"Too many production resources: {num_production} > max {constraints.max_num_machines}")

    num_transport = len(adapters.get_transport_resources(configuration))
    if num_transport > constraints.max_num_transport_resources or num_transport == 0:
        reasons.append(f"Invalid transport resource count: {num_transport} (max: {constraints.max_num_transport_resources}, min: 1)")

    if not valid_num_process_modules(configuration):
        process_counts = {
            resource.ID: len(get_grouped_processes_of_machine(resource, get_possible_production_processes_IDs(configuration)))
            for resource in configuration.resource_data
        }
        over_limit = {rid: cnt for rid, cnt in process_counts.items() if cnt > constraints.max_num_processes_per_machine}
        reasons.append(f"Too many process modules per machine (max {constraints.max_num_processes_per_machine}): {over_limit}")

    try:
        # assert_required_primitives_available(configuration)
        # FIXME: this has to be resolved by asserting dependencies and primitives
        pass
    except ValueError as e:
        reasons.append(f"Required primitives not available: {e}")

    try:
        assert_required_processes_in_resources_available(configuration)
    except ValueError as e:
        reasons.append(f"Required processes not in resources: {e}")

    if not valid_positions(configuration):
        positions = [m.location for m in adapters.get_production_resources(configuration)]
        possible = configuration.scenario_data.options.positions
        reasons.append(f"Invalid positions: resource positions {positions} not all in allowed positions {possible}")

    reconfiguration_cost = get_reconfiguration_cost(
        adapter_object=configuration,
        baseline=base_configuration,
    )
    configuration.reconfiguration_cost = reconfiguration_cost
    if reconfiguration_cost > constraints.max_reconfiguration_cost:
        reasons.append(f"Reconfiguration cost too high: {reconfiguration_cost} > max {constraints.max_reconfiguration_cost}")

    if reasons:
        for reason in reasons:
            log_func(reason)
        return False, reasons

    return True, []


def assert_required_primitives_available(
    configuration: adapters.ProductionSystemData,
) -> bool:
    required_primitives = get_required_primitives(configuration)
    for primitive in required_primitives:
        if not sum(primitive.quantity_in_storages) > 0:
            raise ValueError(f"Required primitive {primitive.ID} is not available.")


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
    is_valid, reasons = check_valid_configuration(adapter_object, base_scenario)
    if not is_valid:
        logging.debug(f"Configuration invalid during evaluation: {'; '.join(reasons)}")
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
