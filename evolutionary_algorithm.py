import json
import time
from random import random

from deap import algorithms, base, creator, tools

from prodsim import sim
from prodsim.optimization_util import (crossover, evaluate, mutation,
                                       random_configuration)
from prodsim.util import set_seed

SEED = 22
NGEN = 50
POPULATION_SIZE = 600
sim.VERBOSE = 1

SAVE_FOLDER = "data/ea_results"

if __name__ == "__main__":

    base_scenario = "data/base_scenario.json"
    with open("data/scenario.json") as json_file:
        scenario_dict = json.load(json_file)

    set_seed(SEED)

    # weights für: (throughput, wip, cost)
    # weights = (0.004, -1.0, -0.0003)
    weights = (0.025, -1.0, -0.001)

    solution_dict = {"current_generation": "00", "00": []}
    performances = {}
    performances["00"] = {}
    start = time.perf_counter()

    creator.create("FitnessMax", base.Fitness, weights=weights)  # als Tupel
    creator.create("Individual", list, fitness=creator.FitnessMax)


    toolbox = base.Toolbox()
    toolbox.register(
        "random_configuration", random_configuration, scenario_dict, base_scenario
    )
    toolbox.register(
        "individual",
        tools.initRepeat,
        creator.Individual,
        toolbox.random_configuration,
        n=1,
    )
    # options_dict = {}


    # Startpopulation erzeugen
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register(
        "evaluate",
        evaluate,
        scenario_dict,
        base_scenario,
        solution_dict,
        performances,
        SAVE_FOLDER,
    )
    toolbox.register("mate", crossover)  # pass
    toolbox.register("mutate", mutation, scenario_dict)
    # toolbox.register('select', tools.selTournament, tournsize=3)
    toolbox.register("select", tools.selNSGA2)
    # toolbox.register('select', tools.selNSGA3)


    population = toolbox.population(n=POPULATION_SIZE)
    fitnesses = toolbox.map(toolbox.evaluate, population)
    generation_performances = []

    for counter, (ind, fit) in enumerate(zip(population, fitnesses)):
        ind.fitness.values = fit
        aggregated_fitness = sum(ind.fitness.wvalues)
        generation_performances.append(aggregated_fitness)
        performances["00"][str(counter)] = {
            "agg_fitness": aggregated_fitness,
            "fitness": [float(value) for value in ind.fitness.values],
            "time_stamp": time.perf_counter() - start
        }

    print("Best Performance: ", max(generation_performances))
    print(
        "Average Performance: ", sum(generation_performances) / len(generation_performances)
    )

    population = toolbox.select(population, len(population))

    for g in range(NGEN):
        print("Generation", g, "________________")
        solution_dict["current_generation"] = str(g)
        solution_dict[str(g)] = []
        performances[str(g)] = {}

        # Vary population
        offspring = tools.selTournamentDCD(population, len(population))
        offspring = [toolbox.clone(ind) for ind in offspring]
        offspring = algorithms.varAnd(offspring, toolbox, cxpb=0.1, mutpb=0.15)

        # Evaluate the individuals
        # invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
        fits = toolbox.map(toolbox.evaluate, offspring)
        generation_performances = []

        for counter, (fit, ind) in enumerate(zip(fits, offspring)):
            ind.fitness.values = fit
            aggregated_fitness = sum(ind.fitness.wvalues)
            generation_performances.append(aggregated_fitness)
            performances[str(g)][str(counter)] = {
                "agg_fitness": aggregated_fitness,
                "fitness": [float(value) for value in ind.fitness.values],
                "time_stamp": time.perf_counter() - start
            }

        print("Best Performance: ", max(generation_performances))
        print(
            "Average Performance: ",
            sum(generation_performances) / len(generation_performances),
        )

        population = toolbox.select(population + offspring, POPULATION_SIZE)

        with open("data/ea_results.json", "w") as json_file:
            json.dump(performances, json_file)
