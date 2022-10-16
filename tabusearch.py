import json
import time
from copy import deepcopy

from Solid.TabuSearch import TabuSearch

from prodsim import env, loader
from prodsim.optimization_util import (check_valid_configuration, crossover,
                                       evaluate, mutation,
                                       random_configuration)
from prodsim.util import set_seed

SEED = 22
env.VERBOSE = 0

SAVE_FOLDER = "data/tabu_results"

base_scenario = "data/base_scenario.json"

with open("data/scenario.json") as json_file:
    scenario_dict = json.load(json_file)

set_seed(SEED)

# weights für: (throughput, wip, throughput_time, cost)
weights = (0.1, -1.0, -1.0, -0.005)

performances = {}
performances["00"] = {}
solution_dict = {"current_generation": "00", "00": []}
start = time.perf_counter()


class Algorithm(TabuSearch):

    def _score(self, state):
        values = evaluate(
            scenario_dict=scenario_dict,
            base_scenario=base_scenario,
            performances=performances,
            solution_dict=solution_dict, 
            save_folder=SAVE_FOLDER,
            individual=[state],
        )

        performance = sum([value * weight for value, weight in zip(values, weights)])
        # print("\n\t########## Evaluted ind", self.counter, "for value:", performance)
        counter = len(performances["00"]) - 1
        print(counter, performance)
        performances["00"][str(counter)] = {
            "agg_fitness": performance,
            "fitness": [float(value) for value in values],
            "time_stamp": time.perf_counter() - start
        }
        with open("data/tabu_results.json", "w") as json_file:
            json.dump(performances, json_file)

        return performance

    def _neighborhood(self):
        neighboarhood = []
        for _ in range(10):
            configuration = mutation(
                scenario_dict=scenario_dict, individual=[deepcopy(self.current)]
            )[0][0]
            base_configuration = loader.CustomLoader()
            base_configuration.read_data(base_scenario, "json")
            if (
                check_valid_configuration(
                    configuration=configuration,
                    base_configuration=base_configuration,
                    scenario_dict=scenario_dict,
                ) and configuration not in neighboarhood
            ):
                neighboarhood.append(configuration)
        
        return neighboarhood


initial_state = loader.CustomLoader()
initial_state.read_data(base_scenario, "json")


alg = Algorithm(initial_state=initial_state, tabu_size=10, max_steps=300, max_score=500)
best_solution, best_objective_value = alg.run()
print("Best solution: ", best_objective_value)

