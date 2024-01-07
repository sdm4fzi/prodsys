import json
import time
from copy import deepcopy

from pydantic import BaseModel, Field
import logging
logger = logging.getLogger(__name__)

from simanneal import Annealer

from prodsys.simulation import sim
from prodsys import adapters
from prodsys.optimization.optimization_util import (
    check_valid_configuration,
    evaluate,
    mutation,
    document_individual,
    get_weights,
    check_breakdown_states_available,
    create_default_breakdown_states
)
from prodsys.util.util import set_seed

sim.VERBOSE = 0


class ProductionSystemOptimization(Annealer):
    def __init__(
        self,
        base_configuration: adapters.ProductionSystemAdapter,
        save_folder: str,
        performances: dict,
        solutions_dict: dict,
        start: float,
        weights: tuple,
        initial_solution: adapters.ProductionSystemAdapter = None,
    ):
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

        performance = sum(
            [value * weight for value, weight in zip(values, self.weights)]
        )
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
    initial_solution_file_path: str = "",
):
    """
    Run a simulated annealing algorithm for configuration optimization.

    Args:
        save_folder (str): Folder to save the results in.
        base_configuration_file_path (str): File path of the serialized base configuration (`prodsys.adapters.JsonProductionSystemAdapter`)
        scenario_file_path (str): File path of the serialized scenario (`prodsys.models.scenario_data.ScenarioData`)
        seed (int): Random seed for optimization.
        Tmax (int): Maximum temperature
        Tmin (int): Minimum temperature
        steps (int): Steps for annealing
        updates (int): Number of updates
        initial_solution_file_path (str, optional): File path to an initial solution. Defaults to "".
    """
    base_configuration = adapters.JsonProductionSystemAdapter()
    base_configuration.read_data(base_configuration_file_path, scenario_file_path)

    if not adapters.check_for_clean_compound_processes(base_configuration):
        logger.info("Compound processes are not clean. This may lead to unexpected results.")
    if not check_breakdown_states_available(base_configuration):
        create_default_breakdown_states(base_configuration)
    if initial_solution_file_path:
        initial_solution = adapters.JsonProductionSystemAdapter()
        initial_solution.read_data(initial_solution_file_path, scenario_file_path)
    else:
        initial_solution = base_configuration.copy(deep=True)

    hyper_parameters = SimulatedAnnealingHyperparameters(
        seed=seed, Tmax=Tmax, Tmin=Tmin, steps=steps, updates=updates)

    simulated_annealing_optimization(
        base_configuration=base_configuration,
        hyper_parameters=hyper_parameters,
        save_folder=save_folder,
        initial_solution=initial_solution        
    )


class SimulatedAnnealingHyperparameters(BaseModel):
    """
    Hyperparameters to perform a configuration optimization with simulated annealing.
    Args:
        seed (int): Seed for random number generator
        Tmax (int): Maximum temperature
        Tmin (int): Minimum temperature
        steps (int): Number of steps
        updates (int): Number of updates
    """
    seed: int = 0
    Tmax: int = 10000
    Tmin: int = 1
    steps: int = 4000
    updates: int = 300

    class Config:
        schema_extra = {
            "example": {
                "summary": "Simulated Annealing Hyperparameters",
                "value": {
                    "seed": 0,
                    "Tmax": 10000,
                    "Tmin": 1,
                    "steps": 4000,
                    "updates": 300,
                },
            }
        }


def simulated_annealing_optimization(
    base_configuration: adapters.ProductionSystemAdapter,
    hyper_parameters: SimulatedAnnealingHyperparameters,
    save_folder: str="results",
    initial_solution: adapters.ProductionSystemAdapter = None,
):
    """
    Optimize a production system configuration using simulated anealing.

    Args:
        base_configuration (adapters.ProductionSystemAdapter): production system to optimize.
        hyper_parameters (SimulatedAnnealingHyperparameters): Hyperparameters for simulated annealing.
        save_folder (str): Folder to save the results in. Defaults to "results".
        initial_solution (adapters.ProductionSystemAdapter, optional): Initial solution for optimization. Defaults to None.
    """
    adapters.ProductionSystemAdapter.Config.validate = False
    adapters.ProductionSystemAdapter.Config.validate_assignment = False
    if not initial_solution:
        initial_solution = base_configuration.copy(deep=True)

    set_seed(hyper_parameters.seed)

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
        initial_solution=initial_solution,
    )

    pso.Tmax = hyper_parameters.Tmax
    pso.Tmin = hyper_parameters.Tmin
    pso.steps = hyper_parameters.steps
    pso.updates = hyper_parameters.updates

    internary, performance = pso.anneal()


def optimize_configuration(
    base_configuration_file_path: str,
    scenario_file_path: str,
    save_folder: str,
    hyper_parameters: SimulatedAnnealingHyperparameters,
):
    """
    Optimize a configuration with simulated annealing.

    Args:
        base_configuration_file_path (str): File path of the serialized base configuration (`prodsys.adapters.JsonProductionSystemAdapter`)
        scenario_file_path (str): File path of the serialized scenario (`prodsys.models.scenario_data.ScenarioData`)
        save_folder (str): Folder to save the results in.
        hyper_parameters (SimulatedAnnealingHyperparameters): Hyperparameters to perform a configuration optimization with simulated annealing.
    """
    run_simulated_annealing(
        save_folder=save_folder,
        base_configuration_file_path=base_configuration_file_path,
        scenario_file_path=scenario_file_path,
        seed=hyper_parameters.seed,
        Tmax=hyper_parameters.Tmax,
        Tmin=hyper_parameters.Tmin,
        steps=hyper_parameters.steps,
        updates=hyper_parameters.updates,
    )
