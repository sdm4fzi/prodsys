import json
import time
from copy import deepcopy

from prodsim.simulation import sim
from prodsim import adapters
from prodsim.util.optimization_util import (
    check_valid_configuration,
    crossover,
    evaluate,
    mutation,
    random_configuration,
    document_individual,
    get_weights,
)
from prodsim.util.util import set_seed
from prodsim.util.tabu_search import TabuSearch

SEED = 22
sim.VERBOSE = 0

SAVE_FOLDER = "data/tabu_results"
BASE_CONFIGURATION_FILE_PATH = "examples/optimization_example/base_scenario.json"
SCENARIO_FILE_PATH = "examples/optimization_example/scenario.json"

base_configuration = adapters.JsonAdapter()
base_configuration.read_data(BASE_CONFIGURATION_FILE_PATH, SCENARIO_FILE_PATH)

set_seed(SEED)

# weights für: (throughput, wip, cost)
# weights = (0.004, -1.0, -0.0003)
# weights = (0.025, -1.0, -0.001)
weights = get_weights(base_configuration, "max")

performances = {}
performances["00"] = {}
solution_dict = {"current_generation": "00", "00": []}
start = time.perf_counter()


class Algorithm(TabuSearch):
    def _score(self, state):
        values = evaluate(
            base_scenario=base_configuration,
            performances=performances,
            solution_dict=solution_dict,
            individual=[state],
        )

        performance = sum([value * weight for value, weight in zip(values, weights)])
        # print("\n\t########## Evaluted ind", self.counter, "for value:", performance)
        counter = len(performances["00"]) - 1
        print(counter, performance)
        document_individual(solution_dict, SAVE_FOLDER, [state])

        performances["00"][str(counter)] = {
            "agg_fitness": performance,
            "fitness": [float(value) for value in values],
            "time_stamp": time.perf_counter() - start,
        }
        with open("data/tabu_results.json", "w") as json_file:
            json.dump(performances, json_file)

        return performance

    def _neighborhood(self):
        neighboarhood = []
        for _ in range(10):
            while True:
                configuration = mutation(individual=[deepcopy(self.current)]
                )[0][0]
                if check_valid_configuration(
                        configuration=configuration,
                        base_configuration=base_configuration,
                    ):
                    neighboarhood.append(configuration)
                    break
        return neighboarhood

alg = Algorithm(initial_state=base_configuration, tabu_size=10, max_steps=300, max_score=500)
best_solution, best_objective_value = alg.run()
print("Best solution: ", best_objective_value)
