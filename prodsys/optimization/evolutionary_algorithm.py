import json
import time
from random import random
from typing import List
from functools import partial
import warnings
import logging
logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=RuntimeWarning)

from os import listdir
from os.path import isfile, join

from deap import algorithms, base, creator, tools
from pydantic import BaseModel, ConfigDict, Field

from prodsys.simulation import sim
from prodsys import adapters
from prodsys.optimization.optimization_util import (
    crossover,
    evaluate,
    mutation,
    random_configuration,
    random_configuration_with_initial_solution,
    document_individual,
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

sim.VERBOSE = 1


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
    solution_dict: dict,
    performances: dict,
    weights: tuple,
    initial_solutions_folder: str,
    hyper_parameters: EvolutionaryAlgorithmHyperparameters,
    full_save_solutions_folder: str="",
):
    creator.create("FitnessMax", base.Fitness, weights=weights)  # als Tupel
    creator.create("Individual", list, fitness=creator.FitnessMax)
    toolbox = base.Toolbox()
    if initial_solutions_folder:
        initial_solutions = read_initial_solutions(
            initial_solutions_folder, base_configuration
        )
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
        solution_dict,
        performances,
        hyper_parameters.number_of_seeds, 
        full_save_solutions_folder
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

    if optimization.VERBOSE:
        print("Best Performance: ", max(generation_performances))
        print(
            "Average Performance: ",
            sum(generation_performances) / len(generation_performances),
        )


def run_evolutionary_algorithm(
    save_folder: str,
    base_configuration_file_path: str,
    scenario_file_path: str,
    full_save: bool,
    seed: int,
    ngen: int,
    population_size: int,
    mutation_rate: float,
    crossover_rate: float,
    n_seeds: int,
    n_processes: int,
):
    """
    Run an evolutionary algorithm for configuration optimization.

    Args:
        save_folder (str): Folder to save the results in.
        base_configuration_file_path (str): File path of the serialized base configuration (`prodsys.adapters.JsonProductionSystemAdapter`)
        scenario_file_path (str): File path of the serialized scenario (`prodsys.models.scenario_data.ScenarioData`)
        full_save (bool): If True, the full event log of solutions is saved. If False, only the KPIs of solutions are saved.
        seed (int): Random seed for optimization.
        ngen (int): Number of generations to run the algorithm.
        population_size (int): Number of individuals in each generation.
        mutation_rate (float): Probability of mutating an individual.
        crossover_rate (float): Probability of crossover between two individuals.
        n_seeds (int): Number of seeds to use for simulation.
        n_processes (int): Number of processes to use for parallelization.
        initial_solutions_folder (str, optional): If specified, the initial solutions are read from this folder and considered in optimization. Defaults to "".
    """
    base_configuration = adapters.JsonProductionSystemAdapter()
    base_configuration.read_data(base_configuration_file_path, scenario_file_path)

    hyper_parameters = EvolutionaryAlgorithmHyperparameters(
        seed=seed,
        number_of_generations=ngen,
        population_size=population_size,
        mutation_rate=mutation_rate,
        crossover_rate=crossover_rate,
        number_of_processes=n_processes,
        number_of_seeds=n_seeds,
    )

    evolutionary_algorithm_optimization(
        base_configuration,
        hyper_parameters,
        save_folder,
        full_save=full_save
    )

def optimize_configuration(
    base_configuration_file_path: str,
    scenario_file_path: str,
    save_folder: str,
    hyper_parameters: EvolutionaryAlgorithmHyperparameters,
    full_save: bool = False,
):
    """
    Optimize a configuration using an evolutionary algorithm.

    Args:
        base_configuration_file_path (str): File path of the serialized base configuration (`prodsys.adapters.JsonProductionSystemAdapter`)
        scenario_file_path (str): File path of the serialized scenario (`prodsys.models.scenario_data.ScenarioData`)
        save_folder (str): Folder to save the results in.
        hyper_parameters (EvolutionaryAlgorithmHyperparameters): Hyperparameters for configuration optimization using an evolutionary algorithm.
    """
    run_evolutionary_algorithm(
        save_folder,
        base_configuration_file_path,
        scenario_file_path,
        full_save,
        hyper_parameters.seed,
        hyper_parameters.number_of_generations,
        hyper_parameters.population_size,
        hyper_parameters.mutation_rate,
        hyper_parameters.crossover_rate,
        hyper_parameters.number_of_processes,
        hyper_parameters.number_of_seeds,
    )

from prodsys.util import util

def evolutionary_algorithm_optimization(
        base_configuration: adapters.ProductionSystemAdapter,
        hyper_parameters: EvolutionaryAlgorithmHyperparameters,
        save_folder: str = "results",
        initial_solutions_folder: str = "",
        full_save: bool = False,
):
    """
    Optimize a production system configuration using an evolutionary algorithm.

    Args:
        base_configuration (adapters.ProductionSystemAdapter): production system to optimize.
        hyper_parameters (EvolutionaryAlgorithmHyperparameters): Hyperparameters for configuration optimization using an evolutionary algorithm.
        save_folder (str): Folder to save the results in. Defaults to "results".
        initial_solutions_folder (str, optional): If specified, the initial solutions are read from this folder and considered in optimization. Defaults to "".
    """
    adapters.ProductionSystemAdapter.model_config["validate_assignment"] = False
    base_configuration = base_configuration.model_copy(deep=True)
    if not adapters.check_for_clean_compound_processes(base_configuration):
        logger.warning("Both compound processes and normal processes are used. This may lead to unexpected results.")
    if not check_breakdown_states_available(base_configuration):
        create_default_breakdown_states(base_configuration)

    util.prepare_save_folder(save_folder + "/")
    set_seed(hyper_parameters.seed)

    weights = get_weights(base_configuration, "max")

    # TODO: rework solution_dict and performances to classes
    solution_dict = {
        "current_generation": "0", 
        "hashes": {} 
    }
    performances = {}
    performances["0"] = {}
    start = time.perf_counter()

    toolbox = register_functions_in_toolbox(
        base_configuration=base_configuration,
        solution_dict=solution_dict,
        performances=performances,
        weights=weights,
        initial_solutions_folder=initial_solutions_folder,
        hyper_parameters=hyper_parameters,
        full_save_solutions_folder=save_folder if full_save else "",
    )

    population = toolbox.population(n=hyper_parameters.population_size)
    if hyper_parameters.number_of_processes > 1:
        pool = Pool(hyper_parameters.number_of_processes)
        toolbox.register("map", pool.map)
    else:
        toolbox.register("map", map)

    fitnesses = toolbox.map(toolbox.evaluate, population)
    save_population_results(
        population, fitnesses, solution_dict, performances, save_folder, start
    )

    population = toolbox.select(population, len(population))

    for g in range(hyper_parameters.number_of_generations):
        current_generation = g + 1
        optimization.VERBOSE = True
        if optimization.VERBOSE:
            print(f"\nGeneration: {current_generation}")
        solution_dict["current_generation"] = str(current_generation)
        performances[str(current_generation)] = {}

        # Vary population
        offspring = tools.selTournamentDCD(population, len(population))
        offspring = [toolbox.clone(ind) for ind in offspring]
        offspring = algorithms.varAnd(
            offspring, toolbox, cxpb=hyper_parameters.crossover_rate, mutpb=hyper_parameters.mutation_rate
        )

        # Evaluate the individuals
        fitnesses = toolbox.map(toolbox.evaluate, offspring)
        save_population_results(
            offspring, fitnesses, solution_dict, performances, save_folder, start
        )

        population = toolbox.select(population + offspring, hyper_parameters.population_size)

        with open(f"{save_folder}/optimization_results.json", "w") as json_file:
            json.dump(performances, json_file)
    if hyper_parameters.number_of_processes > 1:
        pool.close()

