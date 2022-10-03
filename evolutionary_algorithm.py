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
NGEN = 1000
POPULATION_SIZE = 600



base_scenario = 'data/base_scenario.json'
with open('data/scenario.json') as json_file:
        scenario_dict = json.load(json_file)

set_seed(SEED)

#weights für: (logging_time, total_costs, OEE_ges, wip, AOET,)
weights = (300/100000, 1.0, -1.0, 1.0)
creator.create('FitnessMin', base.Fitness, weights=weights) # als Tupel
creator.create('Individual', list, fitness=creator.FitnessMin)




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
toolbox.register('select', tools.selTournament, tournsize=125)
# toolbox.register('select', tools.selNSGA2)


# pool = multiprocessing.Pool(multiprocessing.cpu_count())
# toolbox.register("map", pool.map)

performances = {}

for g in range(NGEN):
    print("Generation", g, "________________")
    # Select the next generation individuals
    invalid_ind = [ind for ind in population if not ind.fitness.valid]
    fits = list(toolbox.map(toolbox.evaluate, invalid_ind))
    # Clone the selected individuals

    generation_performances = []
    performances[str(g)] = {}
    for counter, fit in enumerate(fits):
        agg_fit = 0
        for value, weight in zip(fit, weights):
            agg_fit += value*weight
        agg_fit = float(agg_fit)
        generation_performances.append(agg_fit)
        if agg_fit < 100000:
            performances[str(g)][str(counter)] = {'agg_fitness': agg_fit, 'fitness': [float(value) for value in fit]}
            invalid_ind[counter][0].to_json(f"data/ea_results/f{str(g)}_{str(counter)}.json")
    if not generation_performances:
        generation_performances.append(400000)
    performances[str(g)]['aggregated'] = {'best': min(generation_performances), 'avg': sum(generation_performances) / len(generation_performances)}


    with open("data/ea_results.json", "w") as json_file:
        json.dump(performances, json_file)
    print("Best Performance: ", min(generation_performances))
    print("Average Performance: ", sum(generation_performances) / len(generation_performances))

    for fit, ind in zip(fits, invalid_ind):
        # print('>> ', fit, ' / ', ind)
        ind.fitness.values = fit

    population = toolbox.select(population, len(population))
    population = [toolbox.clone(ind) for ind in population]
    population = algorithms.varAnd(population, toolbox, cxpb=0.1, mutpb=0.1)

for g in range(NGEN):
    print("Generation:", g, "best: ", performances[str(g)]['aggregated']['best'], "average: ", performances[str(g)]['aggregated']['avg'])

