import json
import time
from random import random
import multiprocessing

from deap import algorithms, base, creator, tools

from prodsim.simulation import sim
from prodsim import adapters
from prodsim.util.optimization_util import (
    crossover,
    evaluate,
    mutation,
    random_configuration,
    document_individual,
    arrange_machines
)
from prodsim.util.util import set_seed

SEED = 22
NGEN = 50
POPULATION_SIZE = 40
N_PROCESSES = 8
sim.VERBOSE = 1

SAVE_FOLDER = "data/ea_results"


with open("data/Bosch_scenario.json") as json_file:
    scenario_dict = json.load(json_file)

file_path = "data/adapter_sdm/flexis/Szenario1-84Sek_gut_für_Bosch_reduziert.xlsx"
base_scenario = adapters.FlexisAdapter()

base_scenario.read_data(file_path)
arrange_machines(base_scenario, scenario_dict)

set_seed(SEED)



weights = (
    1, # throughput 750
    -25, # wip 30
    -1/350 # cost 35000
    )

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

# Startpopulation erzeugen
toolbox.register("population", tools.initRepeat, list, toolbox.individual)
toolbox.register(
    "evaluate",
    evaluate,
    scenario_dict,
    base_scenario,
    solution_dict,
    performances,
)
toolbox.register("mate", crossover)  # pass
toolbox.register("mutate", mutation, scenario_dict)
# toolbox.register('select', tools.selTournament, tournsize=3)
toolbox.register("select", tools.selNSGA2)
# toolbox.register('select', tools.selNSGA3)

if __name__ == "__main__":
    print("start")
    population = toolbox.population(n=POPULATION_SIZE)
    print("population")

    pool = multiprocessing.Pool(N_PROCESSES)
    toolbox.register("map", pool.map)
    print("start evaluation")
    fitnesses = toolbox.map(toolbox.evaluate, population)
    pool.close()
    generation_performances = []

    for counter, (ind, fit) in enumerate(zip(population, fitnesses)):
        document_individual(solution_dict, SAVE_FOLDER, ind)
        ind.fitness.values = fit
        aggregated_fitness = sum(ind.fitness.wvalues)
        generation_performances.append(aggregated_fitness)
        performances["00"][ind[0].ID] = {
            "agg_fitness": aggregated_fitness,
            "fitness": [float(value) for value in ind.fitness.values],
            "time_stamp": time.perf_counter() - start,
        }

    print("Best Performance: ", max(generation_performances))
    print(
        "Average Performance: ",
        sum(generation_performances) / len(generation_performances),
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
        pool = multiprocessing.Pool(N_PROCESSES)
        toolbox.register("map", pool.map)
        fits = toolbox.map(toolbox.evaluate, offspring)
        pool.close()
        generation_performances = []

        for counter, (fit, ind) in enumerate(zip(fits, offspring)):
            document_individual(solution_dict, SAVE_FOLDER, ind)
            ind.fitness.values = fit
            aggregated_fitness = sum(ind.fitness.wvalues)
            generation_performances.append(aggregated_fitness)
            performances[str(g)][ind[0].ID] = {
                "agg_fitness": aggregated_fitness,
                "fitness": [float(value) for value in ind.fitness.values],
                "time_stamp": time.perf_counter() - start,
            }

        print("Best Performance: ", max(generation_performances))
        print(
            "Average Performance: ",
            sum(generation_performances) / len(generation_performances),
        )

        population = toolbox.select(population + offspring, POPULATION_SIZE)

        with open("data/ea_results.json", "w") as json_file:
            json.dump(performances, json_file)
