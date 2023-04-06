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

sim.VERBOSE = 0

class ProductionSystemOptimization(Annealer):
    def __init__(self, base_configuration: adapters.Adapter, save_folder: str, performances: dict, solutions_dict: dict, start: float, weights: tuple, initial_solution: adapters.Adapter=None):
        super().__init__(initial_solution, None)
        self.save_folder = save_folder
        self.base_configuration = base_configuration
        self.performances = performances
        self.solution_dict = solutions_dict
        self.start = start
        self.weights = weights

    def move(self):
        while True:
            configuration = mutation(individual=[deepcopy(self.state)])[0][0]
            if check_valid_configuration(
                configuration=configuration,
                base_configuration=self.base_configuration,
            ):
                self.state = configuration
                break

    def energy(self):

        values = evaluate(
            base_scenario=self.base_configuration,
            performances=self.performances,
            solution_dict=self.solution_dict,
            individual=[self.state],
        )

        performance = sum([value * weight for value, weight in zip(values, self.weights)])
        # print("\n\t########## Evaluted ind", self.counter, "for value:", performance)
        counter = len(self.performances["0"]) - 1
        document_individual(self.solution_dict, self.save_folder, [self.state])
        self.performances["0"][str(counter)] = {
            "agg_fitness": performance,
            "fitness": [float(value) for value in values],
            "time_stamp": time.perf_counter() - self.start,
        }
        with open(f"{self.save_folder}/optimization_results.json", "w") as json_file:
            json.dump(self.performances, json_file)

        return performance

def run_simulated_annealing(
    save_folder: str,
    base_configuration_file_path: str,
    scenario_file_path: str,
    seed: int,
    Tmax: int,
    Tmin: int,
    steps: int,
    updates: int,
    initial_solution_file_path: str = ""
):
    base_configuration = adapters.JsonAdapter()
    base_configuration.read_data(base_configuration_file_path, scenario_file_path)

    if initial_solution_file_path:
        initial_solution = adapters.JsonAdapter()
        initial_solution.read_data(initial_solution_file_path, scenario_file_path)
    else:
        initial_solution = base_configuration.copy(deep=True)

    set_seed(seed)

    weights = get_weights(base_configuration, "min")

    solution_dict = {"current_generation": "0", "0": []}
    performances = {}
    performances["0"] = {}
    start = time.perf_counter()

    pso = ProductionSystemOptimization(
        base_configuration=base_configuration,
        save_folder=save_folder,
        performances=performances,
        solutions_dict=solution_dict,
        start=start,
        weights=weights,
        initial_solution=initial_solution)

    pso.Tmax = Tmax
    pso.Tmin = Tmin
    pso.steps = steps
    pso.updates = updates

    internary, performance = pso.anneal()
