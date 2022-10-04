from json import tool
from random import random
from env import Environment
import loader
import print_util
from post_processing import PostProcessor

import multiprocessing
from deap import base, creator, tools, algorithms

from evolutionary import random_configuration, evaluate, mutation, crossover
import json

from util import set_seed

SEED=21
NGEN = 100
POPULATION_SIZE = 250



base_scenario = 'data/base_scenario.json'
with open('data/scenario.json') as json_file:
        scenario_dict = json.load(json_file)

set_seed(SEED)

#weights für: (throughput, wip, throughput_time, cost)
weights = (0.1, -1.0, -1.0, -0.005)
creator.create('FitnessMax', base.Fitness, weights=weights) # als Tupel
creator.create('Individual', list, fitness=creator.FitnessMax)


toolbox = base.Toolbox()
toolbox.register("random_configuration", random_configuration, scenario_dict, base_scenario) 
toolbox.register("individual", tools.initRepeat, creator.Individual, toolbox.random_configuration, n=1)
# options_dict = {}


# Startpopulation erzeugen
toolbox.register("population", tools.initRepeat, list, toolbox.individual)
population = toolbox.population(n=POPULATION_SIZE)

toolbox.register('evaluate', evaluate, scenario_dict, base_scenario)
toolbox.register('mate', crossover) #pass
toolbox.register('mutate', mutation, scenario_dict)
# toolbox.register('select', tools.selTournament, tournsize=3)
toolbox.register('select', tools.selNSGA2)
toolbox.register('select', tools.selNSGA3)


# pool = multiprocessing.Pool(multiprocessing.cpu_count())
# toolbox.register("map", pool.map)

performances = {}

for g in range(NGEN):
    print("Generation", g, "________________")
    # Select the next generation individuals
    invalid_ind = [ind for ind in population if not ind.fitness.valid]
    fits = list(toolbox.map(toolbox.evaluate, invalid_ind))
    # Clone the selected individuals

    for fit, ind in zip(fits, invalid_ind):
        # print('>> ', fit, ' / ', ind)
        ind.fitness.values = fit


    generation_performances = []
    performances[str(g)] = {}
    for counter, ind in enumerate(invalid_ind):
            ind[0].to_json(f"data/ea_results/f{str(g)}_{str(counter)}.json")

    
    generation_performances = []
    for counter, ind in enumerate(population):
        fitness = ind.fitness.values
        aggregated_fitness = sum(ind.fitness.wvalues)
        generation_performances.append(aggregated_fitness)
        performances[str(g)][str(counter)] = {'agg_fitness': aggregated_fitness, 'fitness': [float(value) for value in fitness]}

    performances[str(g)]['aggregated'] = {'best': max(generation_performances), 'avg': sum(generation_performances) / len(generation_performances)}
    print("Best Performance: ", max(generation_performances))
    print("Average Performance: ", sum(generation_performances) / len(generation_performances))

    with open("data/ea_results.json", "w") as json_file:
        json.dump(performances, json_file)

    population = toolbox.select(population, len(population))
    population = [toolbox.clone(ind) for ind in population]
    population = algorithms.varAnd(population, toolbox, cxpb=0.1, mutpb=0.15)

for g in range(NGEN):
    print("Generation:", g, "best: ", performances[str(g)]['aggregated']['best'], "average: ", performances[str(g)]['aggregated']['avg'])
