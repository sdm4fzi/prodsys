from typing import List, Union, Dict, Annotated

from pydantic import parse_obj_as

from fastapi import APIRouter, HTTPException, Body, BackgroundTasks

import json
import prodsys
from prodsys.util import util
from prodsys.optimization import (
    simulated_annealing,
    tabu_search,
    math_opt,
    optimization_analysis,
)
from prodsys.optimization.evolutionary_algorithm import (
    EvolutionaryAlgorithmHyperparameters,
    optimize_configuration,
)
from prodsys.models import performance_indicators
from app.dependencies import (
    prodsys_backend,
    prepare_adapter_from_optimization,
    get_configuration_results_adapter_from_filesystem,
    get_progress_of_optimization,
)


router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/optimize",
    tags=["optimization"],
    responses={404: {"description": "Not found"}},
)

HYPERPARAMETER_EXAMPLES = [
    EvolutionaryAlgorithmHyperparameters.model_config["json_schema_extra"]["examples"][0],
    simulated_annealing.SimulatedAnnealingHyperparameters.model_config["json_schema_extra"][
        "examples"
    ][0],
    tabu_search.TabuSearchHyperparameters.model_config["json_schema_extra"]["examples"][0],
    math_opt.MathOptHyperparameters.model_config["json_schema_extra"]["examples"][0],
]


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
    ]
):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(
            404, f"Adapter {adapter_id} is missing scenario data for optimization."
        )
    configuration_file_path = f"data/{project_id}/{adapter_id}_configuration.json"
    scenario_file_path = f"data/{project_id}/{adapter_id}_scenario.json"
    save_folder = f"data/{project_id}/{adapter_id}"
    
    util.prepare_save_folder(save_folder)
    adapter.write_data(configuration_file_path)
    adapter.write_scenario_data(scenario_file_path)

    # TODO: move this to background task
    if isinstance(hyper_parameters, EvolutionaryAlgorithmHyperparameters):
        optimization_func = optimize_configuration
    elif isinstance(
        hyper_parameters, simulated_annealing.SimulatedAnnealingHyperparameters
    ):
        optimization_func = simulated_annealing.optimize_configuration
    elif isinstance(hyper_parameters, tabu_search.TabuSearchHyperparameters):
        optimization_func = tabu_search.optimize_configuration
    elif isinstance(hyper_parameters, math_opt.MathOptHyperparameters):
        optimization_func = math_opt.optimize_configuration
    else:
        raise HTTPException(404, f"Wrong Hyperparameters for optimization.")

    background_tasks.add_task(
        optimization_func,
        save_folder,
        base_configuration_file_path=configuration_file_path,
        scenario_file_path=scenario_file_path,
        hyper_parameters=hyper_parameters,
    )

    return f"Succesfully optimized configuration of {adapter_id} in {project_id}."


@router.get(
    "/results",
    response_model=Dict[str, Union[Dict[str, List[performance_indicators.KPI_UNION]], str]],
)
def get_optimization_results(project_id: str, adapter_id: str):
    with open(f"data/{project_id}/{adapter_id}/optimization_results.json") as json_file:
        data = json.load(json_file)

    adapter_object = prodsys_backend.get_adapter(project_id, adapter_id)
    kpis = adapter_object.scenario_data.objectives
    
    response = {"solutions": {}}

    for solution in data.values():
        for adapter_name in solution.keys():
            response["solutions"][adapter_name] = []

            for kpi_obj, kpi_value in zip(kpis, solution[adapter_name]["fitness"]):
                kpi_name = kpi_obj.name
                
                kpi_object = parse_obj_as(
                    performance_indicators.KPI_UNION,
                    {
                        "name": kpi_name,
                        "value": kpi_value,
                        "context": [performance_indicators.KPILevelEnum.SYSTEM],
                    },
                )
                response["solutions"][adapter_name].append(kpi_object)

    return response

@router.get(
    "/best_solution",
    response_model=str,
)
def get_best_solution_id(project_id: str, adapter_id: str):
    """
    Returns the best solution ID based on the highest total fitness value from the optimization results.
    """
    try:
        # Open the optimization results file
        with open(f"data/{project_id}/{adapter_id}/optimization_results.json") as json_file:
            data = json.load(json_file)
    except FileNotFoundError:
        raise HTTPException(404, f"Optimization results not found for adapter {adapter_id} in project {project_id}")

    best_solution = None
    best_fitness = float('-inf')  # Initialize with negative infinity

    # Iterate over the solutions in the results file
    for solution in data.values():
        for adapter_name in solution.keys():
            total_fitness = sum(solution[adapter_name]["fitness"])  # Calculate the total fitness value

            # Check if this solution has the best fitness
            if total_fitness > best_fitness:
                best_fitness = total_fitness
                best_solution = adapter_name

    if best_solution is None:
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
    adapter_object = get_configuration_results_adapter_from_filesystem(
        project_id, adapter_id, solution_id
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
    IDs = optimization_analysis.get_pareto_solutions_from_result_files(
        f"data/{project_id}/{adapter_id}/optimization_results.json"
    )
    for solution_id in IDs:
        adapter_object = get_configuration_results_adapter_from_filesystem(
            project_id, adapter_id, solution_id
        )
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
    with open(f"data/{project_id}/{adapter_id}/{solution_id}.json") as json_file:
        data = json.load(json_file)
    return data
