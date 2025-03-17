from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING
import warnings
import logging

from prodsys.optimization.optimization import evaluate_ea_wrapper
from prodsys.optimization.adapter_manipulation import (
    crossover,
    get_random_configuration_asserted,
    mutation,
    random_configuration_with_initial_solution,
)

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
from prodsys.util.util import set_seed, run_from_ipython


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

    model_config = ConfigDict(
        json_schema_extra={
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
        }
    )


def register_functions_in_toolbox(
    base_configuration: adapters.JsonProductionSystemAdapter,
    solutions_dict: dict,
    performances: dict,
    weights: tuple,
    initial_solutions: list[adapters.JsonProductionSystemAdapter],
    hyper_parameters: EvolutionaryAlgorithmHyperparameters,
    full_save: bool,
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
            "random_configuration",
            get_random_configuration_asserted,
            base_configuration,
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
        evaluate_ea_wrapper,
        base_configuration,
        solutions_dict,
        performances,
        hyper_parameters.number_of_seeds,
        full_save
    )
    toolbox.register("mate", crossover)
    toolbox.register("mutate", mutation)

    toolbox.register("select", tools.selNSGA2)

    return toolbox


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
        logger.warning(
            "Both compound processes and normal processes are used. This may lead to unexpected results."
        )
    if not check_breakdown_states_available(base_configuration):
        create_default_breakdown_states(base_configuration)
    hyper_parameters: EvolutionaryAlgorithmHyperparameters = optimizer.hyperparameters
        
    set_seed(hyper_parameters.seed)

    start = time.perf_counter()

    toolbox = register_functions_in_toolbox(
        base_configuration=base_configuration,
        solutions_dict=optimizer.optimization_cache_first_found_hashes,
        performances=optimizer.performances_cache,
        weights=optimizer.weights,
        initial_solutions=optimizer.initial_solutions,
        hyper_parameters=hyper_parameters,
        full_save=optimizer.full_save,
    )

    population = toolbox.population(n=hyper_parameters.population_size)
    if hyper_parameters.number_of_processes > 1:
        pool = Pool(hyper_parameters.number_of_processes)
        toolbox.register("map", pool.map)
    else:
        toolbox.register("map", map)

    fitnesses = toolbox.map(toolbox.evaluate, population)
    for ind, (fit, event_log_dict) in zip(population, fitnesses):
        optimizer.save_optimization_step(fit, ind[0], event_log_dict)
        ind.fitness.values = fit
    population = toolbox.select(population, len(population))

    for g in range(hyper_parameters.number_of_generations):
        current_generation = g + 1
        optimizer.optimization_cache_first_found_hashes.current_generation = str(
            current_generation
        )
        # Vary population
        offspring = tools.selTournamentDCD(population, len(population))
        offspring = [toolbox.clone(ind) for ind in offspring]
        offspring = algorithms.varAnd(
            offspring,
            toolbox,
            cxpb=hyper_parameters.crossover_rate,
            mutpb=hyper_parameters.mutation_rate,
        )

        # Evaluate the individuals
        fitnesses = toolbox.map(toolbox.evaluate, offspring)
        for ind, fit_response in zip(offspring, fitnesses):
            fit, event_log_dict = fit_response
            optimizer.save_optimization_step(fit, ind[0], event_log_dict)
            ind.fitness.values = fit

        population = toolbox.select(
            population + offspring, hyper_parameters.population_size
        )
    if hyper_parameters.number_of_processes > 1:
        pool.close()
