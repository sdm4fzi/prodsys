from imp import source_from_cache
from json import tool
from random import random
from env import Environment
import loader
import print_util
from post_processing import PostProcessor

from copy import deepcopy


from evolutionary import check_valid_configuration, random_configuration, evaluate, mutation, crossover
from simanneal import Annealer


import json

from util import set_seed

SEED=22

SAVE_FOLDER = "data/anneal_results"

base_scenario = 'data/base_scenario.json'

with open('data/scenario.json') as json_file:
        scenario_dict = json.load(json_file)

set_seed(SEED)

#weights für: (throughput, wip, throughput_time, cost)
weights = (-0.1, 1.0, 1.0, 0.005)

performances = {}
performances["00"] = {}
solutions = []

class ProductionSystemOptimization(Annealer):

    def __init__(self, initial_state=None, load_state=None):
        self.counter = 0
        super().__init__(initial_state, load_state)


    def move(self):
        while True:
            # print("Move")
            configuration = mutation(scenario_dict=scenario_dict, individual=[self.state])[0][0]
            base_configuration = loader.CustomLoader()
            base_configuration.read_data(base_scenario, "json")
            if check_valid_configuration(configuration=configuration, base_configuration=base_configuration, scenario_dict=scenario_dict) and configuration.to_dict() not in solutions:
                self.state = configuration
                break

    def energy(self):
        if self.state.to_dict() in solutions:
            print("already simulated")
            index = solutions.index(solutions)
            return performances["00"][str(index)]["agg_fitness"]
        
        solutions.append(self.state.to_dict())
        self.state.to_json(f"{SAVE_FOLDER}/f_{str(self.counter)}.json")
        # print("Found valid Move", self.counter)

        values = evaluate(scenario_dict=scenario_dict, base_scenario=base_scenario, individual=[self.state])
        performance = sum([value*weight for value, weight in zip(values, weights)])
        print("Evaluted ind", self.counter, "for value:", performance)
        performances["00"][str(self.counter)] = {'agg_fitness': performance, "fitness": [float(value) for value in values]}
        with open("data/anneal_results.json", "w") as json_file:
            json.dump(performances, json_file)

        self.counter += 1

        return performance

initial_state = loader.CustomLoader()
initial_state.read_data(base_scenario, "json")
pso = ProductionSystemOptimization(initial_state=initial_state)

internary, performance = pso.anneal()

