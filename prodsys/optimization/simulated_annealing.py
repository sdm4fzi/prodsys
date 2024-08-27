import json
import time
from copy import deepcopy

from pydantic import BaseModel, ConfigDict
import logging

from prodsys.optimization.optimization import evaluate
from prodsys.optimization.adapter_manipulation import mutation
from prodsys.optimization.optimization import check_valid_configuration
from prodsys.optimization.util import document_individual

logger = logging.getLogger(__name__)

from simanneal import Annealer

from prodsys.simulation import sim
from prodsys import adapters
from prodsys.optimization.util import (
    get_weights,
    check_breakdown_states_available,
    create_default_breakdown_states,
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
        number_of_seeds: int = 1,
        initial_solution: adapters.ProductionSystemAdapter = None,
        full_save: bool = False,
    ):
        super().__init__(initial_solution, None)
        self.save_folder = save_folder
        self.base_configuration = base_configuration
        self.performances = performances
        self.solution_dict = solutions_dict
        self.start = start
        self.weights = weights
        self.number_of_seeds = number_of_seeds
        self.full_save = full_save

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
            number_of_seeds=self.number_of_seeds,
            full_save_folder_file_path=self.save_folder if self.full_save else "",
            individual=[self.state],
        )

        performance = sum(
            [value * weight for value, weight in zip(values, self.weights)]
        )
        # print("\n\t########## Evaluted ind", self.counter, "for value:", performance)
        counter = len(self.performances["0"]) - 1
        document_individual(self.solution_dict, self.save_folder, [self.state])
        self.performances["0"][self.state.ID] = {
            "agg_fitness": performance,
            "fitness": [float(value) for value in values],
            "time_stamp": time.perf_counter() - self.start,
            "hash": self.state.hash(),
        }
        with open(f"{self.save_folder}/optimization_results.json", "w") as json_file:
            json.dump(self.performances, json_file)

        return performance


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
    number_of_seeds: int = 1

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "seed": 0,
                    "Tmax": 10000,
                    "Tmin": 1,
                    "steps": 4000,
                    "updates": 300,
                    "number_of_seeds": 1,
                },
            ]
        }
    )


def run_simulated_annealing(
    save_folder: str,
    base_configuration_file_path: str,
    scenario_file_path: str,
    full_save: bool,
    seed: int,
    Tmax: int,
    Tmin: int,
    steps: int,
    updates: int,
    number_of_seeds: int,
    initial_solution_file_path: str = "",
):
    """
    Run a simulated annealing algorithm for configuration optimization.

    Args:
        save_folder (str): Folder to save the results in.
        base_configuration_file_path (str): File path of the serialized base configuration (`prodsys.adapters.JsonProductionSystemAdapter`)
        scenario_file_path (str): File path of the serialized scenario (`prodsys.models.scenario_data.ScenarioData`)
        full_save (bool): Save the full results of the optimization.
        seed (int): Random seed for optimization.
        Tmax (int): Maximum temperature
        Tmin (int): Minimum temperature
        steps (int): Steps for annealing
        updates (int): Number of updates
        number_of_seeds (int): Number of seeds for optimization
        initial_solution_file_path (str, optional): File path to an initial solution. Defaults to "".
    """
    base_configuration = adapters.JsonProductionSystemAdapter()
    base_configuration.read_data(base_configuration_file_path, scenario_file_path)
    if not base_configuration.ID:
        base_configuration.ID = "base_configuration"

    if initial_solution_file_path:
        initial_solution = adapters.JsonProductionSystemAdapter()
        initial_solution.read_data(initial_solution_file_path, scenario_file_path)
        if not initial_solution.ID:
            initial_solution.ID = "initial_solution"
    else:
        initial_solution = base_configuration.model_copy(deep=True)

    hyper_parameters = SimulatedAnnealingHyperparameters(
        seed=seed,
        Tmax=Tmax,
        Tmin=Tmin,
        steps=steps,
        updates=updates,
        number_of_seeds=number_of_seeds,
    )

    simulated_annealing_optimization(
        base_configuration=base_configuration,
        hyper_parameters=hyper_parameters,
        save_folder=save_folder,
        initial_solution=initial_solution,
        full_save=full_save,
    )


def simulated_annealing_optimization(
    base_configuration: adapters.ProductionSystemAdapter,
    hyper_parameters: SimulatedAnnealingHyperparameters,
    save_folder: str = "results",
    initial_solution: adapters.ProductionSystemAdapter = None,
    full_save: bool = False,
):
    """
    Optimize a production system configuration using simulated anealing.

    Args:
        base_configuration (adapters.ProductionSystemAdapter): production system to optimize.
        hyper_parameters (SimulatedAnnealingHyperparameters): Hyperparameters for simulated annealing.
        save_folder (str): Folder to save the results in. Defaults to "results".
        initial_solution (adapters.ProductionSystemAdapter, optional): Initial solution for optimization. Defaults to None.
    """
    adapters.ProductionSystemAdapter.model_config["validate_assignment"] = False
    if not adapters.check_for_clean_compound_processes(base_configuration):
        logger.warning(
            "Both compound processes and normal processes are used. This may lead to unexpected results."
        )
    if not check_breakdown_states_available(base_configuration):
        create_default_breakdown_states(base_configuration)
    if not initial_solution:
        initial_solution = base_configuration.model_copy(deep=True)

    set_seed(hyper_parameters.seed)

    weights = get_weights(base_configuration, "min")

    solution_dict = {"current_generation": "0", "hashes": {}}
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
        number_of_seeds=hyper_parameters.number_of_seeds,
        initial_solution=initial_solution,
        full_save=full_save,
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
    full_save: bool = False,
):
    """
    Optimize a configuration with simulated annealing.

    Args:
        base_configuration_file_path (str): File path of the serialized base configuration (`prodsys.adapters.JsonProductionSystemAdapter`)
        scenario_file_path (str): File path of the serialized scenario (`prodsys.models.scenario_data.ScenarioData`)
        save_folder (str): Folder to save the results in.
        hyper_parameters (SimulatedAnnealingHyperparameters): Hyperparameters to perform a configuration optimization with simulated annealing.
        full_save (bool, optional): Save the full results of the optimization. Defaults to False.
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
        number_of_seeds=hyper_parameters.number_of_seeds,
        full_save=full_save,
    )
