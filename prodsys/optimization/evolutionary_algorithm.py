from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING
import warnings
import logging

from prodsys.optimization.optimization import evaluate
from prodsys.optimization.adapter_manipulation import crossover, mutation, random_configuration, random_configuration_with_initial_solution
from prodsys.optimization.util import document_individual
logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=RuntimeWarning)

from deap import algorithms, base, creator, tools
from pydantic import BaseModel, ConfigDict, Field

from prodsys.simulation import sim
from prodsys import adapters
from prodsys.optimization.util import (
    get_weights,
    check_breakdown_states_available,
    create_default_breakdown_states,
)
from prodsys.util.util import set_seed, read_initial_solutions, run_from_ipython
from prodsys import optimization


if run_from_ipython():
    from multiprocessing.pool import ThreadPool as Pool
else:
    from multiprocessing.pool import Pool


if TYPE_CHECKING:
    from prodsys.optimization.optimizer import Optimizer


creator.create("FitnessMax", base.Fitness, weights=(1, 1, 1))  # als Tupel
creator.create("Individual", list, fitness=creator.FitnessMax)

class EvolutionaryAlgorithmHyperparameters(BaseModel):
    """
    Hyperparameters for configuration optimization using an evolutionary algorithm.

    Args:
        seed (int): Seed for the random number generator.
        number_of_generations (int): Number of generations to run the algorithm.
        population_size (int): Number of individuals in each generation.
        mutation_rate (float): Probability of mutating an individual.
        crossover_rate (float): Probability of crossover between two individuals.
        number_of_seeds (int): Number of seeds to use for simulation.
        number_of_processes (int): Number of processes to use for parallelization.
    """

    seed: int = Field(0, description="Seed for the random number generator.")
    number_of_generations: int = 10
    population_size: int = 10
    mutation_rate: float = 0.1
    crossover_rate: float = 0.1
    number_of_seeds: int = 1
    number_of_processes: int = 1

    model_config=ConfigDict(json_schema_extra={
        "examples": [
            {
                "seed": 0,
                "number_of_generations": 10,
                "population_size": 10,
                "mutation_rate": 0.1,
                "crossover_rate": 0.1,
                "number_of_seeds": 1,
                "number_of_processes": 1,
            },
        ]
    })

def register_functions_in_toolbox(
    base_configuration: adapters.JsonProductionSystemAdapter,
    solutions_dict: dict,
    performances: dict,
    weights: tuple,
    initial_solutions: list[adapters.JsonProductionSystemAdapter],
    hyper_parameters: EvolutionaryAlgorithmHyperparameters,
    full_save_solutions_folder: str = "",
):
    creator.create("FitnessMax", base.Fitness, weights=weights)  # als Tupel
    creator.create("Individual", list, fitness=creator.FitnessMax)
    toolbox = base.Toolbox()
    if initial_solutions:
        toolbox.register(
            "random_configuration",
            random_configuration_with_initial_solution,
            initial_solutions,
        )
    else:
        toolbox.register(
            "random_configuration", random_configuration, base_configuration
        )
    toolbox.register(
        "individual",
        tools.initRepeat,
        creator.Individual,
        toolbox.random_configuration,
        n=1,
    )

    # Startpopulation erzeugen
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register(
        "evaluate",
        evaluate,
        base_configuration,
        solutions_dict,
        performances,
        hyper_parameters.number_of_seeds,
        full_save_solutions_folder,
    )
    toolbox.register("mate", crossover)
    toolbox.register("mutate", mutation)

    toolbox.register("select", tools.selNSGA2)

    return toolbox


def save_population_results(
    population, fitnesses, solution_dict, performances, save_folder, start
):
    generation_performances = []

    for ind, fit in zip(population, fitnesses):
        document_individual(solution_dict, save_folder, ind)
        ind.fitness.values = fit
        aggregated_fitness = sum(ind.fitness.wvalues)
        generation_performances.append(aggregated_fitness)
        performances[str(solution_dict["current_generation"])][ind[0].ID] = {
            "agg_fitness": aggregated_fitness,
            "fitness": [float(value) for value in ind.fitness.values],
            "time_stamp": time.perf_counter() - start,
            "hash": ind[0].hash(),
        }

    # if optimization.VERBOSE:
    #     print("Best Performance: ", max(generation_performances))
    #     print(
    #         "Average Performance: ",
    #         sum(generation_performances) / len(generation_performances),
    #     )


from prodsys.util import util

def evolutionary_algorithm_optimization(
        optimizer: "Optimizer",
):
    """
    Optimize a production system configuration using an evolutionary algorithm.

    Args:
        optimizer (Optimizer): The optimizer that contains the adapter, hyperparameters, and initial solutions.
    """
    adapters.ProductionSystemAdapter.model_config["validate_assignment"] = False

    base_configuration = optimizer.adapter.model_copy(deep=True)
    if not adapters.check_for_clean_compound_processes(base_configuration):
        logger.warning("Both compound processes and normal processes are used. This may lead to unexpected results.")
    if not check_breakdown_states_available(base_configuration):
        create_default_breakdown_states(base_configuration)
    hyper_parameters: EvolutionaryAlgorithmHyperparameters = optimizer.hyperparameters

    if optimizer.save_folder:
        util.prepare_save_folder(optimizer.save_folder + "/")
    set_seed(hyper_parameters.seed)

    weights = get_weights(base_configuration, "max")

    # # TODO: rework solution_dict and performances to classes
    # solution_dict = {
    #     "current_generation": "0",
    #     "hashes": {}
    # }
    # performances = {}
    # performances["0"] = {}
    start = time.perf_counter()

    solutions_dict = optimizer.solutions_dict
    performances = optimizer.performances

    toolbox = register_functions_in_toolbox(
        base_configuration=base_configuration,
        solutions_dict=solutions_dict,
        performances=optimizer.performances,
        weights=weights,
        initial_solutions=optimizer.initial_solutions,
        hyper_parameters=hyper_parameters,
        full_save_solutions_folder=optimizer.save_folder if optimizer.full_save else "",
    )

    population = toolbox.population(n=hyper_parameters.population_size)
    if hyper_parameters.number_of_processes > 1:
        pool = Pool(hyper_parameters.number_of_processes)
        toolbox.register("map", pool.map)
    else:
        toolbox.register("map", map)

    fitnesses = toolbox.map(toolbox.evaluate, population)
    for fitness in fitnesses:
        optimizer.update_progress()
    save_population_results(
        population, fitnesses, solutions_dict, performances, optimizer.save_folder, start
    )
    population = toolbox.select(population, len(population))

    for g in range(hyper_parameters.number_of_generations):
        current_generation = g + 1
        # optimization.VERBOSE = True
        # if optimization.VERBOSE:
        #     print(f"\nGeneration: {current_generation}")
        solutions_dict["current_generation"] = str(current_generation)
        performances[str(current_generation)] = {}

    #     # Vary population
        offspring = tools.selTournamentDCD(population, len(population))
        offspring = [toolbox.clone(ind) for ind in offspring]
        offspring = algorithms.varAnd(
            offspring, toolbox, cxpb=hyper_parameters.crossover_rate, mutpb=hyper_parameters.mutation_rate
        )

    #     # Evaluate the individuals
        fitnesses = toolbox.map(toolbox.evaluate, offspring)
        for fitness in fitnesses:
            optimizer.update_progress()
        save_population_results(
                offspring, fitnesses, solutions_dict, performances, optimizer.save_folder, start
            )

        population = toolbox.select(population + offspring, hyper_parameters.population_size)
        if optimizer.save_folder:
            with open(f"{optimizer.save_folder}/optimization_results.json", "w") as json_file:
                json.dump(performances, json_file)
    if hyper_parameters.number_of_processes > 1:
        pool.close()
