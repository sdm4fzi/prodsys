from typing import List, Union, Dict, Annotated

from pydantic import TypeAdapter

from fastapi import APIRouter, HTTPException, Body, BackgroundTasks
from app.models.progress_report import ProgressReport

import os
import json
import prodsys
from prodsys.util import util
from prodsys.optimization import (
    simulated_annealing,
    tabu_search,
    math_opt,
    optimization_analysis,
)
from prodsys.optimization.util import (
    get_weights,
)
from prodsys.optimization.evolutionary_algorithm import (
    EvolutionaryAlgorithmHyperparameters,
)
from prodsys.optimization.tabu_search import TabuSearchHyperparameters
from prodsys.optimization.simulated_annealing import SimulatedAnnealingHyperparameters
from prodsys.optimization.math_opt import MathOptHyperparameters
from prodsys.models import performance_indicators
from app.dependencies import (
    prodsys_backend,
    prepare_adapter_from_optimization,
    get_progress_of_optimization,
)
from prodsys.optimization.optimizer import FileSystemSaveOptimizer, Optimizer


router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/optimize",
    tags=["optimization"],
    responses={404: {"description": "Not found"}},
)

HYPERPARAMETER_EXAMPLES = [
    EvolutionaryAlgorithmHyperparameters.model_config["json_schema_extra"]["examples"][
        0
    ],
    simulated_annealing.SimulatedAnnealingHyperparameters.model_config[
        "json_schema_extra"
    ]["examples"][0],
    tabu_search.TabuSearchHyperparameters.model_config["json_schema_extra"]["examples"][
        0
    ],
    math_opt.MathOptHyperparameters.model_config["json_schema_extra"]["examples"][0],
]

# Global instance of the optimizer
optimizer_cache: Dict[str, Optimizer] = {}


def get_optimizer(project_id: str, adapter_id: str) -> Optimizer:
    # TODO: move this function probably to the backend code or to the dependencies!
    if (project_id, adapter_id) not in optimizer_cache:
        save_folder = f"data/{project_id}/{adapter_id}/optimization_results/"
        # maybe move these functions to the backend to save the complete optimizer and make it easily changeable in the future with mongo db or so
        optimizer = FileSystemSaveOptimizer(
            adapter=prodsys_backend.get_adapter(project_id, adapter_id),
            hyperparameters=prodsys_backend.get_last_optimizer_hyperparameters(
                project_id, adapter_id
            ),
            save_folder=save_folder,
            initial_solutions=None,
            full_save=True,
        )
        optimizer_cache[(project_id, adapter_id)] = optimizer
    return optimizer_cache[(project_id, adapter_id)]


def set_optimizer_in_cache(project_id: str, adapter_id: str, optimizer: Optimizer):
    optimizer_cache[(project_id, adapter_id)] = (
        optimizer  # Saves Opti. for specific adapter ID and project_id
    )


@router.post(
    "/",
    response_model=str,
)
async def optimize(
    project_id: str,
    adapter_id: str,
    background_tasks: BackgroundTasks,
    hyper_parameters: Annotated[
        Union[
            EvolutionaryAlgorithmHyperparameters,
            simulated_annealing.SimulatedAnnealingHyperparameters,
            tabu_search.TabuSearchHyperparameters,
            math_opt.MathOptHyperparameters,
        ],
        Body(examples=HYPERPARAMETER_EXAMPLES),
    ],
):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(
            404,
            f"Adapter {adapter_id} in project {project_id} is missing scenario data for optimization.",
        )
    save_folder = f"data/{project_id}/{adapter_id}/optimization_results"

    util.prepare_save_folder(save_folder)
    # TODO: maybe allow later also to insert initial solutions to optimization or use existing best solutions to further optimize

    prodsys_backend.save_optimizer_hyperparameters(
        project_id, adapter_id, hyper_parameters
    )
    optimizer = FileSystemSaveOptimizer(
        adapter=adapter,
        hyperparameters=hyper_parameters,
        initial_solutions=None,
        save_folder=save_folder,
        full_save=True,
    )

    # name this optimizer cache, maybe delete it, if access is easier with backend usage
    set_optimizer_in_cache(project_id, adapter_id, optimizer)

    background_tasks.add_task(optimizer.optimize)

    return f"Succesfully optimized configuration of {adapter_id} in {project_id}."


@router.get(
    "/optimization_progress",
    response_model=ProgressReport,
)
async def get_optimization_progress(project_id: str, adapter_id: str) -> ProgressReport:
    try:
        optimizer = get_optimizer(project_id, adapter_id)
    except ValueError as e:
        raise HTTPException(
            404,
            f"Optimization progress cannot be found, because optimizer is not available in cache. Start optimization for. {adapter_id} in {project_id} first.",
        )
    optimizer = get_optimizer(project_id, adapter_id)
    return get_progress_of_optimization(optimizer)


@router.get(
    "/results",
    response_model=Dict[str, Dict[str, List[performance_indicators.KPI_UNION]]],
)
def get_optimization_results(project_id: str, adapter_id: str):
    optimizer = get_optimizer(project_id, adapter_id)

    response = {"solutions": {}}
    for generation, fitness_entry in optimizer.get_optimization_results().items():
        for adapter_id, fitness_data in fitness_entry.items():
            response["solutions"][adapter_id] = []

            for kpi_name, kpi_value in zip(
                fitness_data.objective_names, fitness_data.fitness
            ):

                kpi_object = TypeAdapter(
                    performance_indicators.KPI_UNION
                ).validate_python(
                    {
                        "name": kpi_name,
                        "value": kpi_value,
                        "context": [performance_indicators.KPILevelEnum.SYSTEM],
                    },
                )
                response["solutions"][adapter_id].append(kpi_object)

    return response


@router.get(
    "/best_solution",
    response_model=str,
)
def get_best_solution_id(project_id: str, adapter_id: str) -> str:
    """
    Returns the best solution ID based on the highest total fitness value from the optimization results.
    """
    optimizer = get_optimizer(project_id, adapter_id)
    if isinstance(
        optimizer.hyperparameters,
        (EvolutionaryAlgorithmHyperparameters, TabuSearchHyperparameters),
    ):
        direction = "max"
    elif isinstance(
        optimizer.hyperparameters,
        SimulatedAnnealingHyperparameters,
        MathOptHyperparameters,
    ): 
        direction = "min"

    weights = get_weights(optimizer.adapter, direction)

    # TODO: move this calculations to a function and also make it optional to normalize kpis
    best_solution = None
    best_fitness = float("-inf")  # Initialize with negative infinity
    # num_objectives = 3  # Number of objectives in the optimization - WIP, Throughput, WIP
    min_values = [float("inf")] * len(weights)
    max_values = [float("-inf")] * len(weights)

    # 1. Find the best solution based on the weighted fitness value from the optimization
    for solution in optimizer.get_optimization_results().values():
        for adapter_name in solution.keys():
            agg_fitness = solution[adapter_name].get("agg_fitness", None)
            if agg_fitness == -300000.0:
                continue

            fitness_values = solution[adapter_name]["fitness"]

            for i in range(len(weights)):
                min_values[i] = min(min_values[i], fitness_values[i])
                max_values[i] = max(max_values[i], fitness_values[i])

    for solution in optimizer.get_optimization_results().values():
        for adapter_name in solution.keys():
            fitness_values = solution[adapter_name]["fitness"]
            if agg_fitness == -300000.0:
                continue

            fitness_values = solution[adapter_name]["fitness"]

            normalized_fitness = []
            for i in range(len(weights)):
                if max_values[i] == min_values[i]:
                    normalized_value = 0.5
                else:
                    normalized_value = (fitness_values[i] - min_values[i]) / (
                        max_values[i] - min_values[i]
                    )
                normalized_fitness.append(normalized_value)

            solution[adapter_name]["fitness_normalized"] = normalized_fitness

            weighted_fitness = sum(w * f for w, f in zip(weights, normalized_fitness))

            if weighted_fitness > best_fitness:
                best_fitness = weighted_fitness
                best_solution = adapter_name
                best_fitness_values = fitness_values

    # 2. Check the KPIs from the initial solution which was used for the simulation run.
    try:
        original_kpis = prodsys_backend.get_performance(project_id, adapter_id)

        wip_value = None
        throughput_value = None

        for kpi in original_kpis:
            if kpi["name"].lower() == "wip" and "all_products" in kpi["context"]:
                wip_value = kpi["value"]
            if kpi["name"].lower() == "output":
                throughput_value = kpi["value"]

        if (
            best_fitness_values[0] > 0
            and best_fitness_values[1] < throughput_value
            and best_fitness_values[2] > wip_value
            or best_solution is None
        ):
            best_solution = "initial_simulation"

    except Exception as e:
        pass

    if best_solution is None or best_solution == "initial_simulation":
        print(
            f"No valid or better solution then the start configuration found! Increase the number runs of optimization significantly or loose the constraints."
        )
        raise HTTPException(404, "No valid solution found.")

    return best_solution


@router.get(
    "/register/{solution_id}",
    tags=["optimization"],
    response_model=str,
)
def register_adapter_with_evaluation(
    project_id: str, adapter_id: str, solution_id: str
):
    optimizer = get_optimizer(project_id, adapter_id)
    adapter_object = optimizer.get_optimization_result_configuration(
        solution_id
    )
    prepare_adapter_from_optimization(
        adapter_object, project_id, adapter_id, solution_id
    )

    return (
        "Sucessfully registered and ran simulation for adapter with ID: " + solution_id
    )


@router.get(
    "/pareto_front_performances",
    tags=["optimization"],
    response_model=str,
)
def get_optimization_pareto_front(project_id: str, adapter_id: str):
    optimizer = get_optimizer(project_id, adapter_id)
    IDs = optimization_analysis.get_pareto_solutions_from_result_files(optimizer.get_optimization_results())
    for solution_id in IDs:
        adapter_object = optimizer.get_optimization_result_configuration(solution_id)
        prepare_adapter_from_optimization(
            adapter_object, project_id, adapter_id, solution_id
        )

    return (
        "Succesfully found pareto front, registered and ran simulations for pareto adapters with IDs: "
        + str(IDs)
    )


@router.get(
    "/{solution_id}",
    tags=["optimization"],
    response_model=prodsys.adapters.JsonProductionSystemAdapter,
)
def get_optimization_solution(
    project_id: str, adapter_id: str, solution_id: str
) -> prodsys.adapters.JsonProductionSystemAdapter:
    optimizer = get_optimizer(project_id, adapter_id)
    return optimizer.get_optimization_result_configuration(solution_id)
