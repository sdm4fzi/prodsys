import json
import time
from copy import deepcopy

from simanneal import Annealer

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

SEED = 22
sim.VERBOSE = 0

SAVE_FOLDER = "data/anneal_results"
BASE_CONFIGURATION_FILE_PATH = "examples/optimization_example/base_scenario.json"
SCENARIO_FILE_PATH = "examples/optimization_example/scenario.json"

base_configuration = adapters.JsonAdapter()
base_configuration.read_data(BASE_CONFIGURATION_FILE_PATH, SCENARIO_FILE_PATH)

set_seed(SEED)


# weights für: (throughput, wip, cost)
# weights = (-0.004, 1.0, 0.0003)
# weights = (-0.025, 1.0, 0.001)
weights = get_weights(base_configuration, "min")

performances = {}
performances["00"] = {}
solution_dict = {"current_generation": "00", "00": []}
start = time.perf_counter()

# TODO: get Annealer packakge, include in requirements and import here
class ProductionSystemOptimization(Annealer):
    def __init__(self, initial_state=None, load_state=None):
        super().__init__(initial_state, load_state)

    def move(self):
        while True:
            # print("Move")
            configuration = mutation(individual=[deepcopy(self.state)])[0][0]
            if check_valid_configuration(
                configuration=configuration,
                base_configuration=base_configuration,
            ):
                self.state = configuration
                break

    def energy(self):

        values = evaluate(
            base_scenario=base_configuration,
            performances=performances,
            solution_dict=solution_dict,
            individual=[self.state],
        )

        performance = sum([value * weight for value, weight in zip(values, weights)])
        # print("\n\t########## Evaluted ind", self.counter, "for value:", performance)
        counter = len(performances["00"]) - 1
        document_individual(solution_dict, SAVE_FOLDER, [self.state])
        performances["00"][str(counter)] = {
            "agg_fitness": performance,
            "fitness": [float(value) for value in values],
            "time_stamp": time.perf_counter() - start,
        }
        with open("data/anneal_results.json", "w") as json_file:
            json.dump(performances, json_file)

        return performance


pso = ProductionSystemOptimization(initial_state=base_configuration)

# pso.auto(minutes=240)
# {'tmax': 7500.0, 'tmin': 0.67, 'steps': 1500, 'updates': 100} 64:27:53ä'


pso.Tmax = 10000
pso.Tmin = 0.67
pso.steps = 4000
pso.updates = 300

internary, performance = pso.anneal()
