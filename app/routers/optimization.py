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
    EvolutionaryAlgorithmHyperparameters
)
from prodsys.optimization.tabu_search import (
    TabuSearchHyperparameters
)
from prodsys.optimization.simulated_annealing import (
    SimulatedAnnealingHyperparameters
)
from prodsys.optimization.math_opt import (
    MathOptHyperparameters
)
from prodsys.models import performance_indicators
from app.dependencies import (
    prodsys_backend,
    prepare_adapter_from_optimization,
    get_configuration_results_adapter_from_filesystem,
    get_progress_of_optimization,
)
from prodsys.optimization.optimizer import Optimizer


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

# Global instance of the optimizer
optimizers: Dict[str, Optimizer] = {}

def set_optimizer(project_id: str, adapter_id: str, optimizer: Optimizer):
    optimizers[(project_id, adapter_id)] = optimizer #Saves Opti. for specific adapter ID and project_id

def get_current_optimizer(project_id: str, adapter_id: str) -> Optimizer:
    if (project_id, adapter_id) not in optimizers:
        raise HTTPException(404, f"Optimizer for Adapter {adapter_id} in project {project_id} wasn't initialized.")
    return optimizers[(project_id, adapter_id)]

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
            404, f"Adapter {adapter_id} in project {project_id} is missing scenario data for optimization."
        )
    configuration_file_path = f"data/{project_id}/{adapter_id}_configuration.json"
    scenario_file_path = f"data/{project_id}/{adapter_id}_scenario.json"
    save_folder = f"data/{project_id}/{adapter_id}"
    
    util.prepare_save_folder(save_folder)
    adapter.write_data(configuration_file_path)
    adapter.write_scenario_data(scenario_file_path)

    optimizer = Optimizer(
        adapter=adapter,
        hyperparameters=hyper_parameters,
        save_folder=save_folder
    )
    
    set_optimizer(project_id, adapter_id, optimizer)

    background_tasks.add_task(
        optimizer.optimize
    )

    return f"Succesfully optimized configuration of {adapter_id} in {project_id}."

@router.get(
    "/optimization_progress",
    response_model=ProgressReport,
)
async def get_optimization_progress(project_id: str, adapter_id: str) -> ProgressReport:
    optimizer = get_current_optimizer(project_id, adapter_id)
    return get_progress_of_optimization(optimizer)


@router.get(
    "/results",
    response_model=Dict[str, Dict[str, List[performance_indicators.KPI_UNION]]],
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
                
                kpi_object = TypeAdapter(performance_indicators.KPI_UNION).validate_python(
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
    
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    hyperparameters = get_current_optimizer(project_id, adapter_id).hyperparameters
    if isinstance(hyperparameters, (EvolutionaryAlgorithmHyperparameters, TabuSearchHyperparameters)): 
        direction = "max"
    elif isinstance(hyperparameters, SimulatedAnnealingHyperparameters,  MathOptHyperparameters): #TODO: Check case for math_opt - should me min because costs are minimized
        direction = "min"

    weights = get_weights(adapter, direction)

    best_solution = None
    best_fitness = float('-inf')  # Initialize with negative infinity
    num_objectives = 3  # Number of objectives in the optimization - WIP, Throughput, WIP
    min_values = [float('inf')] * num_objectives
    max_values = [float('-inf')] * num_objectives

    for solution in data.values():
        for adapter_name in solution.keys():
            agg_fitness = solution[adapter_name].get("agg_fitness", None)
            if agg_fitness == -300000.0:
                continue

            fitness_values = solution[adapter_name]["fitness"]

            for i in range(num_objectives):
                min_values[i] = min(min_values[i], fitness_values[i])
                max_values[i] = max(max_values[i], fitness_values[i]) 

    for solution in data.values():
        for adapter_name in solution.keys():  
            fitness_values = solution[adapter_name]["fitness"]
            if agg_fitness == -300000.0:
                continue

            fitness_values = solution[adapter_name]["fitness"]

            normalized_fitness = []
            for i in range(num_objectives):
                if max_values[i] == min_values[i]:
                    normalized_value = 0.5
                else:
                    normalized_value = (fitness_values[i] - min_values[i]) / (max_values[i] - min_values[i])
                normalized_fitness.append(normalized_value)

            solution[adapter_name]["fitness_normalized"] = normalized_fitness
            
            weighted_fitness = sum(w * f for w, f in zip(weights, normalized_fitness))

            if weighted_fitness > best_fitness:
                best_fitness = weighted_fitness
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
    folder_path = f"data/{project_id}/{adapter_id}/"
    #Check if there is a matching file in the folder. 
    for filename in os.listdir(folder_path):
        #If there is a file, it is getting loaded and the loop is closed.
        if solution_id in filename and filename.endswith(".json"):
            with open(os.path.join(folder_path, filename)) as json_file:
                data = json.load(json_file)
            return data 
    
    raise FileNotFoundError(f"I couldn`t find a file for solution ID {solution_id} in {folder_path}.")
