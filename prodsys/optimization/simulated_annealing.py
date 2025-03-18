import json
import time
from copy import deepcopy
from typing import TYPE_CHECKING
from prodsys.util import util
from pydantic import BaseModel, ConfigDict
import logging

from prodsys.optimization.optimization import evaluate
from prodsys.optimization.adapter_manipulation import mutation
from prodsys.optimization.optimization import check_valid_configuration
# from prodsys.optimization.util import document_individual

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

if TYPE_CHECKING:
    from prodsys.optimization.optimizer import Optimizer


class ProductionSystemOptimization(Annealer):
    def __init__(
        self,
        optimizer: "Optimizer",
        base_configuration: adapters.ProductionSystemAdapter,
        performances: dict,
        solutions_dict: dict,
        start: float,
        weights: tuple,
        number_of_seeds: int = 1,
        initial_solution: adapters.ProductionSystemAdapter = None,
        full_save: bool = False,
    ):
        super().__init__(initial_solution, None)
        self.optimizer = optimizer
        self.save_folder = optimizer.save_folder
        self.base_configuration = base_configuration
        self.performances = performances
        self.solution_dict = solutions_dict
        self.start = start
        self.weights = weights
        self.number_of_seeds = number_of_seeds
        self.full_save = full_save
        self.previous_counter = None

    def default_update(self, step, T, E, acceptance, improvement):
        # ignore this function, it is only here to overwrite the print of the super class...
        pass

    def move(self):
        while True:
            configuration = mutation(individual=[deepcopy(self.state)])[0][0]
            if check_valid_configuration(
                configuration=configuration,
                base_configuration=self.base_configuration,
            ):
                self.state: adapters.ProductionSystemAdapter = configuration
                break

    def energy(self):
        fitness_values, event_log_dict = evaluate(
            base_scenario=self.base_configuration,
            solution_dict=self.solution_dict,
            number_of_seeds=self.number_of_seeds,
            adapter_object=self.state,
            full_save=self.full_save,
        )

        counter = len(self.performances["0"]) - 1
        if self.previous_counter is not None:
            fitness_values, event_log_dict = self.optimizer.save_optimization_step(
                fitness_values=fitness_values,
                configuration=self.state,
                event_log_dict=event_log_dict,
            )
        performance = sum(
            [value * weight for value, weight in zip(fitness_values, self.weights)]
        )
        self.previous_counter = counter
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


def simulated_annealing_optimization(optimizer: "Optimizer"):
    """
    Optimize a production system configuration using simulated anealing.

    Args:
        base_configuration (adapters.ProductionSystemAdapter): production system to optimize.
        hyper_parameters (SimulatedAnnealingHyperparameters): Hyperparameters for simulated annealing.
        save_folder (str): Folder to save the results in. Defaults to "results".
        initial_solution (adapters.ProductionSystemAdapter, optional): Initial solution for optimization. Defaults to None.
    """
    adapters.ProductionSystemAdapter.model_config["validate_assignment"] = False
    base_configuration = optimizer.adapter.model_copy(deep=True)

    if not adapters.check_for_clean_compound_processes(base_configuration):
        logger.warning(
            "Both compound processes and normal processes are used. This may lead to unexpected results."
        )
    if not check_breakdown_states_available(base_configuration):
        create_default_breakdown_states(base_configuration)
    if not optimizer.initial_solutions:
        optimizer.initial_solutions = base_configuration.model_copy(deep=True)

    hyper_parameters: SimulatedAnnealingHyperparameters = optimizer.hyperparameters

    set_seed(hyper_parameters.seed)

    start = time.perf_counter()
    solutions_dict = optimizer.optimization_cache_first_found_hashes
    performances = optimizer.performances_cache

    pso = ProductionSystemOptimization(
        optimizer=optimizer,
        base_configuration=base_configuration,
        performances=performances,
        solutions_dict=solutions_dict,
        start=start,
        weights=optimizer.weights,
        number_of_seeds=hyper_parameters.number_of_seeds,
        initial_solution=optimizer.initial_solutions,
        full_save=optimizer.save_folder if optimizer.full_save else "",
    )

    pso.Tmax = hyper_parameters.Tmax
    pso.Tmin = hyper_parameters.Tmin
    pso.steps = hyper_parameters.steps
    pso.updates = hyper_parameters.updates

    internary, performance = pso.anneal()
