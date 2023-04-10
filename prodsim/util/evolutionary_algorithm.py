import json
import time
from random import random
import multiprocessing
from typing import List
from functools import partial
import warnings

warnings.filterwarnings("ignore", category=RuntimeWarning)

from os import listdir
from os.path import isfile, join

from deap import algorithms, base, creator, tools
from pydantic import BaseModel

from prodsim.simulation import sim
from prodsim import adapters
from prodsim.util.optimization_util import (
    crossover,
    evaluate,
    mutation,
    random_configuration,
    random_configuration_with_initial_solution,
    document_individual,
    get_weights,
)
from prodsim.util.util import set_seed, read_initial_solutions


sim.VERBOSE = 1

creator.create("FitnessMax", base.Fitness, weights=(1, 1, 1))  # als Tupel
creator.create("Individual", list, fitness=creator.FitnessMax)


def register_functions_in_toolbox(
    base_configuration: adapters.JsonAdapter,
    solution_dict: dict,
    performances: dict,
    weights: tuple,
    initial_solutions_folder: str
):
    creator.create("FitnessMax", base.Fitness, weights=weights)  # als Tupel
    creator.create("Individual", list, fitness=creator.FitnessMax)
    toolbox = base.Toolbox()
    if initial_solutions_folder:
        initial_solutions = read_initial_solutions(initial_solutions_folder, base_configuration)
        toolbox.register("random_configuration", random_configuration_with_initial_solution, initial_solutions)
    else:
        toolbox.register("random_configuration", random_configuration, base_configuration)
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
    )
    toolbox.register("mate", crossover)
    toolbox.register("mutate", mutation)

    # TODO: make this as a parameter
    # toolbox.register('select', tools.selTournament, tournsize=3)
    toolbox.register("select", tools.selNSGA2)
    # toolbox.register('select', tools.selNSGA3)

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
        }

    print("Best Performance: ", max(generation_performances))
    print(
        "Average Performance: ",
        sum(generation_performances) / len(generation_performances),
    )


def run_evolutionary_algorithm(
    save_folder: str,
    base_configuration_file_path: str,
    scenario_file_path: str,
    seed: int,
    ngen: int,
    population_size: int,
    mutation_rate: float,
    crossover_rate: float,
    n_processes: int,
    initial_solutions_folder: str = ""
):
    base_configuration = adapters.JsonAdapter()
    base_configuration.read_data(base_configuration_file_path, scenario_file_path)

    set_seed(seed)

    weights = get_weights(base_configuration, "max")

    solution_dict = {"current_generation": "0", "0": []}
    performances = {}
    performances["0"] = {}
    start = time.perf_counter()

    toolbox = register_functions_in_toolbox(
        base_configuration=base_configuration,
        solution_dict=solution_dict,
        performances=performances,
        weights=weights,
        initial_solutions_folder=initial_solutions_folder
    )

    population = toolbox.population(n=population_size)

    pool = multiprocessing.Pool(n_processes)
    toolbox.register("map", pool.map)

    fitnesses = toolbox.map(toolbox.evaluate, population)
    save_population_results(
        population, fitnesses, solution_dict, performances, save_folder, start
    )

    population = toolbox.select(population, len(population))

    for g in range(ngen):
        current_generation = g + 1
        print("Generation", current_generation, "________________")
        solution_dict["current_generation"] = str(current_generation)
        solution_dict[str(current_generation)] = []
        performances[str(current_generation)] = {}

        # Vary population
        offspring = tools.selTournamentDCD(population, len(population))
        offspring = [toolbox.clone(ind) for ind in offspring]
        offspring = algorithms.varAnd(offspring, toolbox, cxpb=crossover_rate, mutpb=mutation_rate)

        # Evaluate the individuals
        fitnesses = toolbox.map(toolbox.evaluate, offspring)
        save_population_results(
            offspring, fitnesses, solution_dict, performances, save_folder, start
        )

        population = toolbox.select(population + offspring, population_size)

        with open(f"{save_folder}/optimization_results.json", "w") as json_file:
            json.dump(performances, json_file)
    pool.close()

class EvolutionaryAlgorithmHyperparameters(BaseModel):
    seed: int
    number_of_generations: int
    population_size: int
    mutation_rate: float
    crossover_rate: float
    number_of_processes: int

def optimize_configuration(
    base_configuration_file_path: str,
    scenario_file_path: str,
    save_folder: str,
    hyper_parameters: EvolutionaryAlgorithmHyperparameters
):  
    run_evolutionary_algorithm(
        save_folder,
        base_configuration_file_path,
        scenario_file_path,
        hyper_parameters.seed,
        hyper_parameters.number_of_generations,
        hyper_parameters.population_size,
        hyper_parameters.mutation_rate,
        hyper_parameters.crossover_rate,
        hyper_parameters.number_of_processes
    )
