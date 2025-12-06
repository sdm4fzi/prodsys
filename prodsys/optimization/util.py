"""
Module containts utility functions for the optimization module. These functions can be used to change the production system configuration and evaluate its performance.
"""

from __future__ import annotations

from typing import Dict, List, Union, Tuple, Literal
from enum import Enum
import logging

from prodsys.express.state import ProcessBreakdownState
from prodsys.models.primitives_data import PrimitiveData
from prodsys.models.dependency_data import DependencyType

logger = logging.getLogger(__name__)
from pydantic import TypeAdapter

from prodsys import adapters
from prodsys.models.production_system_data import get_possible_production_processes_IDs
from prodsys.models import (
    processes_data,
    resource_data,
    state_data,
    performance_indicators,
    time_model_data,
)


class BreakdownStateNamingConvention(str, Enum):
    MACHINE_BREAKDOWN_STATE = "BSM"
    TRANSPORT_RESOURCE_BREAKDOWN_STATE = "BST"
    PROCESS_MODULE_BREAKDOWN_STATE = "BSP"


def get_breakdown_state_ids_of_machine_with_processes(
    processes: List[str], adapter_object: adapters.ProductionSystemData
) -> List[str]:
    state_ids = []
    if check_breakdown_state_available(
        adapter_object, BreakdownStateNamingConvention.MACHINE_BREAKDOWN_STATE.value
    ):
        state_ids.append(BreakdownStateNamingConvention.MACHINE_BREAKDOWN_STATE.value)
    for process_id in processes:
        process_breakdown_state_id = f"{BreakdownStateNamingConvention.PROCESS_MODULE_BREAKDOWN_STATE.value}_{process_id}"
        if check_breakdown_state_available(adapter_object, process_breakdown_state_id):
            state_ids.append(process_breakdown_state_id)
    return state_ids


def get_required_primitives(
    adapter_object: adapters.ProductionSystemData,
) -> List[PrimitiveData]:
    """
    Function that returns the required primitives for the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        List[PrimitiveData]: List of required primitives
    """
    dependency_ids = set()
    for product in adapter_object.product_data:
        dependency_ids.update(product.dependency_ids)
    if not dependency_ids:
        return []
    primitive_dependencies = [
        dependency.required_entity for dependency in adapter_object.depdendency_data if dependency.dependency_type == DependencyType.TOOL
    ]
    primitives = [
        primitive for primitive in adapter_object.primitive_data if primitive.ID in primitive_dependencies
    ]
    return primitives


def check_breakdown_state_available(
    adapter_object: adapters.ProductionSystemData, breakdown_state_id: str
) -> bool:
    """
    Function that checks if breakdown states are available in the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if breakdown states are available, False otherwise.
    """
    breakdown_state_ids = set(
        [
            state.ID
            for state in adapter_object.state_data
            if isinstance(state, state_data.BreakDownStateData)
            or isinstance(state, state_data.ProcessBreakDownStateData)
        ]
    )
    if breakdown_state_id not in breakdown_state_ids:
        return False
    return True


def check_process_breakdown_state_available(
    adapter_object: adapters.ProductionSystemData,
) -> bool:
    """
    Function that checks if process breakdown states are available in the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if process breakdown states are available, False otherwise.
    """
    process_ids = [
        process.ID
        for process in adapter_object.process_data
        if isinstance(process, processes_data.ProductionProcessData)
    ]
    for process_id in process_ids:
        process_breakdown_state_id = f"{BreakdownStateNamingConvention.PROCESS_MODULE_BREAKDOWN_STATE.value}_{process_id}"
        if not check_breakdown_state_available(
            adapter_object, process_breakdown_state_id
        ):
            return False
    return True


def check_breakdown_states_available(
    adapter_object: adapters.ProductionSystemData,
) -> bool:
    """
    Function that checks if breakdown states are available in the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        bool: True if breakdown states are available, False otherwise.
    """
    if (
        not check_breakdown_state_available(
            adapter_object, BreakdownStateNamingConvention.MACHINE_BREAKDOWN_STATE.value
        )
        or not check_breakdown_state_available(
            adapter_object,
            BreakdownStateNamingConvention.TRANSPORT_RESOURCE_BREAKDOWN_STATE.value,
        )
        or not check_process_breakdown_state_available(adapter_object)
    ):
        return False
    return True


def check_heterogenous_time_models(
    time_models: List[time_model_data.TIME_MODEL_DATA],
) -> bool:
    """
    Function that checks if heterogenous time models are present in the list.

    Args:
        time_models (List[time_model_data.TIME_MODEL_DATA]): List of time models.

    Returns:
        bool: True if heterogenous time models are available, False otherwise.
    """
    # TODO: update this function to use new time models and not the deprecated ones...
    if all(
        isinstance(time_model, time_model_data.FunctionTimeModelData)
        for time_model in time_models
    ):
        parameters = []
        for time_model in time_models:
            parameters.append(
                (
                    round(time_model.location),
                    round(time_model.scale),
                    time_model.distribution_function,
                )
            )
        if len(set(parameters)) == 1:
            return True
    # elif all(
    #     isinstance(time_model, time_model_data.SequentialTimeModelData)
    #     for time_model in time_models
    # ):
    #     sequences = []
    #     for time_model in time_models:
    #         sequences.append(tuple(time_model.sequence))
    #     if len(set(sequences)) == 1:
    #         return True
    # elif all(
    #     isinstance(time_model, time_model_data.ManhattanDistanceTimeModelData)
    #     for time_model in time_models
    # ):
    #     parameters = []
    #     for time_model in time_models:
    #         parameters.append((time_model.speed, time_model.reaction_time))
    #     if len(set(parameters)) == 1:
    #         return True
    return False


def check_states_for_heterogenous_time_models(
    states: List[
        Union[state_data.BreakDownStateData, state_data.ProcessBreakDownStateData]
    ],
    adapter_object: adapters.ProductionSystemData,
) -> bool:
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
        breakdown_time_models.append(
            [
                time_model
                for time_model in all_time_models
                if time_model.ID == state.time_model_id
            ].pop()
        )
        repair_time_models.append(
            [
                time_model
                for time_model in all_time_models
                if time_model.ID == state.repair_time_model_id
            ].pop()
        )
    return check_heterogenous_time_models(
        breakdown_time_models
    ) and check_heterogenous_time_models(repair_time_models)


def create_default_breakdown_states(adapter_object: adapters.ProductionSystemData):
    logger.info(f"Trying to create default breakdown states.")
    breakdown_states = [
        state
        for state in adapter_object.state_data
        if isinstance(state, state_data.BreakDownStateData)
    ]
    process_breakdown_states = [
        state
        for state in adapter_object.state_data
        if isinstance(state, state_data.ProcessBreakDownStateData)
    ]
    machines = adapters.get_production_resources(adapter_object)
    transport_resources = adapters.get_transport_resources(adapter_object)
    machine_breakdown_states = [
        state
        for state in breakdown_states
        if any(state.ID in machine.state_ids for machine in machines)
    ]
    transport_resource_breakdown_states = [
        state
        for state in breakdown_states
        if any(
            state.ID in transport_resource.state_ids
            for transport_resource in transport_resources
        )
    ]
    process_breakdown_states = [
        state
        for state in process_breakdown_states
        if any(
            state.ID in machine.state_ids and state.process_id in machine.process_ids
            for machine in machines
        )
    ]
    if machine_breakdown_states and not check_breakdown_state_available(
        adapter_object, BreakdownStateNamingConvention.MACHINE_BREAKDOWN_STATE.value
    ):
        if not check_states_for_heterogenous_time_models(
            machine_breakdown_states, adapter_object
        ):
            raise ValueError(
                f"The machine breakdown states are not heterogenous and it is not ambiguous which state should be the Breakdownstate. Please check the time models or define a distinct machine breakdown state called {BreakdownStateNamingConvention.MACHINE_BREAKDOWN_STATE.value}."
            )
        machine_breakdown_state = machine_breakdown_states[0].model_copy(deep=True)
        machine_breakdown_state.ID = (
            BreakdownStateNamingConvention.MACHINE_BREAKDOWN_STATE.value
        )
        adapter_object.state_data.append(machine_breakdown_state)
        logger.info(
            f"Added default breakdown state for production resources to the production system."
        )
    if transport_resource_breakdown_states and not check_breakdown_state_available(
        adapter_object,
        BreakdownStateNamingConvention.TRANSPORT_RESOURCE_BREAKDOWN_STATE.value,
    ):
        if not check_states_for_heterogenous_time_models(
            transport_resource_breakdown_states, adapter_object
        ):
            raise ValueError(
                f"The transport resource breakdown states are not heterogenous and it is not ambiguous which state should be the Breakdownstate. Please check the time models or define a distinct transport resource breakdown state called {BreakdownStateNamingConvention.TRANSPORT_RESOURCE_BREAKDOWN_STATE.value}."
            )
        transport_resource_breakdown_state = transport_resource_breakdown_states[
            0
        ].model_copy(deep=True)
        transport_resource_breakdown_state.ID = (
            BreakdownStateNamingConvention.TRANSPORT_RESOURCE_BREAKDOWN_STATE.value
        )
        adapter_object.state_data.append(transport_resource_breakdown_state)
        logger.info(
            f"Added default breakdown state for transport resources to the production system."
        )
    if process_breakdown_states:
        process_breakdown_states_by_process_id = {}
        for state in process_breakdown_states:
            process_breakdown_states_by_process_id[state.process_id] = (
                process_breakdown_states_by_process_id.get(state.process_id, [])
                + [state]
            )
        for (
            process_id,
            process_breakdown_states_for_process,
        ) in process_breakdown_states_by_process_id.items():
            if check_breakdown_state_available(
                adapter_object,
                f"{BreakdownStateNamingConvention.PROCESS_MODULE_BREAKDOWN_STATE.value}_{process_id}",
            ):
                continue
            if not check_states_for_heterogenous_time_models(
                process_breakdown_states_for_process, adapter_object
            ):
                raise ValueError(
                    f"The process breakdown states are not heterogenous and it is not ambiguous which state should be the Breakdownstate. Please check the time models or define a distinct process breakdown state called {BreakdownStateNamingConvention.PROCESS_MODULE_BREAKDOWN_STATE}."
                )
            process_breakdown_state: ProcessBreakdownState = (
                process_breakdown_states_for_process[0].model_copy()
            )
            process_breakdown_state.ID = f"{BreakdownStateNamingConvention.PROCESS_MODULE_BREAKDOWN_STATE.value}_{process_id}"
            adapter_object.state_data.append(process_breakdown_state)
            logger.info(
                f"Added default breakdown state for process modules to the production system."
            )


def clean_out_breakdown_states_of_resources(
    adapter_object: adapters.ProductionSystemData,
):
    for resource in adapter_object.resource_data:
        if isinstance(resource, resource_data.ResourceData) and any(
            True
            for state in adapter_object.state_data
            if state.ID == BreakdownStateNamingConvention.MACHINE_BREAKDOWN_STATE.value
            or BreakdownStateNamingConvention.PROCESS_MODULE_BREAKDOWN_STATE.value
            in state.ID
        ):
            resource.state_ids = get_breakdown_state_ids_of_machine_with_processes(
                resource.process_ids, adapter_object
            )
        elif isinstance(resource, resource_data.ResourceData) and any(
            True
            for state in adapter_object.state_data
            if state.ID
            == BreakdownStateNamingConvention.TRANSPORT_RESOURCE_BREAKDOWN_STATE.value
        ):
            resource.state_ids = [
                BreakdownStateNamingConvention.TRANSPORT_RESOURCE_BREAKDOWN_STATE.value
            ]


def get_weights(
    adapter: adapters.ProductionSystemData, direction: Literal["min", "max"]
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
        kpi: performance_indicators.KPI_UNION = TypeAdapter(
            performance_indicators.KPI_UNION
        ).validate_python({"name": objective.name})
        if kpi.target != direction:
            weights.append(objective.weight * -1)
        else:
            weights.append(objective.weight)
    return tuple(weights)


def add_setup_states_to_machine(
    adapter_object: adapters.ProductionSystemData, machine_id: str
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


def get_grouped_processes_of_machine(
    machine: resource_data.ResourceData,
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
    adapter_object: adapters.ProductionSystemData,
) -> Dict[Tuple[str], int]:
    possible_processes = get_possible_production_processes_IDs(adapter_object)
    num_of_process_modules = {}
    for process in possible_processes:
        if isinstance(process, str):
            process = tuple([process])
        num_of_process_modules[process] = 0
    for machine in adapters.get_production_resources(adapter_object):
        machine_processes = get_grouped_processes_of_machine(
            machine, possible_processes
        )
        for process in machine_processes:
            num_of_process_modules[process] += 1
    return num_of_process_modules


def adjust_process_capacities(
    adapter_object: adapters.ProductionSystemData,
) -> adapters.ProductionSystemData:
    """
    Function that adjusts the process capacities of the production system.

    Args:
        adapter_object (adapters.ProductionSystemAdapter): Production system configuration with specified scenario data.

    Returns:
        adapters.ProductionSystemAdapter: Production system configuration with adjusted process capacities.
    """
    for resource in adapter_object.resource_data:
        resource.process_capacities = [resource.capacity] * len(resource.process_ids)


# def document_individual(
#     solution_dict: Dict[str, Union[list, str]],
#     save_folder: str,
#     individual,
# ):
#     adapter_object: adapters.ProductionSystemAdapter = individual[0]
#     current_generation = solution_dict["current_generation"]

#     if adapter_object.hash() not in solution_dict["hashes"]:
#         solution_dict["hashes"][adapter_object.hash()] = {
#             "generation": current_generation,
#             "ID": adapter_object.ID,
#         }
#     if save_folder:
#         adapters.ProductionSystemData.model_validate(adapter_object).write_data(
#             f"{save_folder}/generation_{current_generation}_{adapter_object.ID}.json"
#         )
