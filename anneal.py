import json
import time
from copy import deepcopy

from simanneal import Annealer

from prodsim import env, loader
from prodsim.optimization_util import (check_valid_configuration, crossover,
                                       evaluate, mutation,
                                       random_configuration)
from prodsim.util import set_seed

SEED = 22
env.VERBOSE = 0

SAVE_FOLDER = "data/anneal_results"

base_scenario = "data/base_scenario.json"

with open("data/scenario.json") as json_file:
    scenario_dict = json.load(json_file)

set_seed(SEED)

# weights für: (throughput, wip, cost)
# weights = (-0.004, 1.0, 0.0003)
weights = (-0.025, 1.0, 0.001)

performances = {}
performances["00"] = {}
solution_dict = {"current_generation": "00", "00": []}
start = time.perf_counter()


class ProductionSystemOptimization(Annealer):
    def __init__(self, initial_state=None, load_state=None):
        super().__init__(initial_state, load_state)

    def move(self):
        while True:
            # print("Move")
            configuration = mutation(
                scenario_dict=scenario_dict, individual=[deepcopy(self.state)]
            )[0][0]
            base_configuration = loader.CustomLoader()
            base_configuration.read_data(base_scenario, "json")
            if (
                check_valid_configuration(
                    configuration=configuration,
                    base_configuration=base_configuration,
                    scenario_dict=scenario_dict,
                )
            ):
                self.state = configuration
                break

    def energy(self):

        values = evaluate(
            scenario_dict=scenario_dict,
            base_scenario=base_scenario,
            performances=performances,
            solution_dict=solution_dict, 
            save_folder=SAVE_FOLDER,
            individual=[self.state],
        )

        performance = sum([value * weight for value, weight in zip(values, weights)])
        # print("\n\t########## Evaluted ind", self.counter, "for value:", performance)
        counter = len(performances["00"]) - 1
        performances["00"][str(counter)] = {
            "agg_fitness": performance,
            "fitness": [float(value) for value in values],
            "time_stamp": time.perf_counter() - start
        }
        with open("data/anneal_results.json", "w") as json_file:
            json.dump(performances, json_file)


        return performance


initial_state = loader.CustomLoader()
initial_state.read_data(base_scenario, "json")
pso = ProductionSystemOptimization(initial_state=initial_state)

# pso.auto(minutes=240)
# {'tmax': 7500.0, 'tmin': 0.67, 'steps': 1500, 'updates': 100} 64:27:53ä'


pso.Tmax = 10000
pso.Tmin = 0.67
pso.steps = 4000
pso.updates = 300

internary, performance = pso.anneal()

