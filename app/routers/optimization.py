from typing import List, Union, Dict, Annotated

from pydantic import parse_obj_as

from fastapi import APIRouter, HTTPException, Body

import json
import prodsys
from prodsys.util import util
from prodsys.optimization import (
    simulated_annealing,
    tabu_search,
    math_opt,
    optimization_analysis,
)
from prodsys.optimization.evolutionary_algorithm import EvolutionaryAlgorithmHyperparameters, optimize_configuration
from prodsys.models import (
    performance_indicators
)
from app.dependencies import get_adapter, prepare_adapter_from_optimization, get_configuration_results_adapter_from_filesystem


router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/optimize",
    tags=["optimization"],
    responses={404: {"description": "Not found"}},
)

HYPERPARAMETER_EXAMPLES = {
    "Evolutionary algorithm": EvolutionaryAlgorithmHyperparameters.Config.schema_extra["example"],
    "Simulated annealing": simulated_annealing.SimulatedAnnealingHyperparameters.Config.schema_extra["example"],
    "Tabu search": tabu_search.TabuSearchHyperparameters.Config.schema_extra["example"],
    "Mathematical optimization": math_opt.MathOptHyperparameters.Config.schema_extra["example"],
}

@router.post(
    "/",
    response_model=str,
)
async def run_configuration_optimization(
    project_id: str,
    adapter_id: str,
    hyper_parameters: Annotated[Union[
        EvolutionaryAlgorithmHyperparameters,
        simulated_annealing.SimulatedAnnealingHyperparameters,
        tabu_search.TabuSearchHyperparameters,
        math_opt.MathOptHyperparameters,
    ], Body(examples=HYPERPARAMETER_EXAMPLES)],
):
    adapter = get_adapter(project_id, adapter_id)
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

    if isinstance(
        hyper_parameters, EvolutionaryAlgorithmHyperparameters
    ):
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

    optimization_func(
        save_folder=save_folder,
        base_configuration_file_path=configuration_file_path,
        scenario_file_path=scenario_file_path,
        hyper_parameters=hyper_parameters,
    )
    return f"Succesfully optimized configuration of {adapter_id} in {project_id}."


@router.get(
    "/results",
    response_model=Dict[str, List[performance_indicators.KPI_UNION]],
)
def get_optimization_results(project_id: str, adapter_id: str):
    with open(f"data/{project_id}/{adapter_id}/optimization_results.json") as json_file:
        data = json.load(json_file)
    adapter_object = get_adapter(project_id, adapter_id)
    kpis = adapter_object.scenario_data.objectives
    response = {}
    for solution in data.values():
        for adapter_name in solution.keys():
            response[adapter_name] = []
            for kpi_name, kpi_value in zip(kpis, solution[adapter_name]["fitness"]):
                kpi_object = parse_obj_as(
                    performance_indicators.KPI_UNION,
                    {
                        "name": kpi_name,
                        "value": kpi_value,
                        "context": [performance_indicators.KPILevelEnum.SYSTEM],
                    },
                )
                response[adapter_name].append(kpi_object)
    return response


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
