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


base_scenario = 'data/base_scenario.json'
with open('data/scenario.json') as json_file:
        scenario_dict = json.load(json_file)

#weights für: (logging_time, total_costs, OEE_ges, wip, AOET,)
creator.create('FitnessMin', base.Fitness, weights=(-1.0, -1.0)) # als Tupel
creator.create('Individual', list, fitness=creator.FitnessMin)




toolbox = base.Toolbox()
toolbox.register("random_configuration", random_configuration, base_scenario, scenario_dict) 
toolbox.register("individual", tools.initRepeat, creator.Individual, toolbox.random_configuration, n=1)
# options_dict = {}


# Startpopulation erzeugen
toolbox.register("population", tools.initRepeat, list, toolbox.individual)
population = toolbox.population(n=20)

toolbox.register('evaluate', evaluate)


toolbox.register('mate', crossover) #pass
toolbox.register('mutate', mutation)
toolbox.register('select', tools.selTournament, tournsize=3)
# toolbox.register('select', tools.selNSGA2)

NGEN = 10

# pool = multiprocessing.Pool(multiprocessing.cpu_count())
# toolbox.register("map", pool.map)

for g in range(NGEN):
    # Select the next generation individuals
    offspring = algorithms.varAnd(population, toolbox, cxpb=0.5, mutpb=0.1)
    fits = toolbox.map(toolbox.evaluate, offspring)
    # Clone the selected individuals

    for fit, ind in zip(fits, offspring):
        # print('>> ', fit, ' / ', ind)
        ind.fitness.values = fit

    population = toolbox.select(offspring, k=len(population))