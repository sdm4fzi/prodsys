from abc import ABCMeta, abstractmethod
from copy import deepcopy
from random import randint, random, shuffle
from collections import deque
from numpy import argmax

import logging
logger = logging.getLogger(__name__)

import json
import time

from pydantic import BaseModel, ConfigDict, Field

from prodsys.simulation import sim
from prodsys import adapters
from prodsys.optimization.optimization_util import (
    check_valid_configuration,
    crossover,
    evaluate,
    mutation,
    random_configuration,
    document_individual,
    get_weights,
    check_breakdown_states_available,
    create_default_breakdown_states
)
from prodsys.util.util import set_seed


class TabuSearch:

    __metaclass__ = ABCMeta

    cur_steps = None

    tabu_size = None
    tabu_list = None

    initial_state = None
    current = None
    best = None

    max_steps = None
    max_score = None

    def __init__(self, initial_state, tabu_size, max_steps, max_score=None):
        self.initial_state = initial_state

        if isinstance(tabu_size, int) and tabu_size > 0:
            self.tabu_size = tabu_size
        else:
            raise TypeError("Tabu size must be a positive integer")

        if isinstance(max_steps, int) and max_steps > 0:
            self.max_steps = max_steps
        else:
            raise TypeError("Maximum steps must be a positive integer")

        if max_score is not None:
            if isinstance(max_score, (int, float)):
                self.max_score = float(max_score)
            else:
                raise TypeError("Maximum score must be a numeric type")

    def __str__(self):
        return (
            "TABU SEARCH: \n"
            + "CURRENT STEPS: %d \n"
            + "BEST SCORE: %f \n"
            + "BEST MEMBER: %s \n\n"
        ) % (self.cur_steps, self._score(self.best), str(self.best))

    def __repr__(self):
        return self.__str__()

    def _clear(self):
        """
        Resets the variables that are altered on a per-run basis of the algorithm

        :return: None
        """
        self.cur_steps = 0
        self.tabu_list = deque(maxlen=self.tabu_size)
        self.current = self.initial_state
        self.best = self.initial_state

    @abstractmethod
    def _score(self, state):
        pass

    @abstractmethod
    def _neighborhood(self):
        pass

    def _best(self, neighborhood):
        return neighborhood[argmax([self._score(x) for x in neighborhood])]

    def run(self, verbose=True):
        self._clear()
        for i in range(self.max_steps):
            self.cur_steps += 1

            if ((i + 1) % 100 == 0) and verbose:
                print(self)

            neighborhood = self._neighborhood()
            neighborhood_best = self._best(neighborhood)

            while True:
                if all([x in self.tabu_list for x in neighborhood]):
                    print("TERMINATING - NO SUITABLE NEIGHBORS")
                    return self.best, self._score(self.best)
                if neighborhood_best in self.tabu_list:
                    if self._score(neighborhood_best) > self._score(self.best):
                        self.tabu_list.append(neighborhood_best)
                        self.best = deepcopy(neighborhood_best)
                        break
                    else:
                        neighborhood.remove(neighborhood_best)
                        neighborhood_best = self._best(neighborhood)
                else:
                    self.tabu_list.append(neighborhood_best)
                    self.current = neighborhood_best
                    if self._score(self.current) > self._score(self.best):
                        self.best = deepcopy(self.current)
                    break

            if self.max_score is not None and self._score(self.best) > self.max_score:
                print("TERMINATING - REACHED MAXIMUM SCORE")
                return self.best, self._score(self.best)
        print("TERMINATING - REACHED MAXIMUM STEPS")
        return self.best, self._score(self.best)
    

class TabuSearchHyperparameters(BaseModel):
    """
    Hyperparameters for configuration optimization with tabu search.


    Args:
        seed (int): Seed for random number generator
        tabu_size (int): Size of tabu list
        max_steps (int): Maximum number of steps
        max_score (float): Maximum score
    """

    seed: int = 0
    tabu_size: int = 10
    max_steps: int = 300
    max_score: float = 500
    number_of_seeds: int = 1

    model_config=ConfigDict(json_schema_extra={
        "examples": [
            {
                "seed": 0,
                "tabu_size": 10,
                "max_steps": 300,
                "max_score": 500,
                "number_of_seeds": 1,
            },
        ]
    })


def run_tabu_search(
    save_folder: str,
    base_configuration_file_path: str,
    scenario_file_path: str,
    seed: int,
    tabu_size: int,
    max_steps: int,
    max_score: float,
    number_of_seeds: int = 1,
    initial_solution_file_path: str = "",
    full_save: bool = False,
):
    """
    Runs tabu search optimization.

    Args:
        save_folder (str): Folder to save the results in.
        base_configuration_file_path (str): File path of the serialized base configuration (`prodsys.adapters.JsonProductionSystemAdapter`)
        scenario_file_path (str): File path of the serialized scenario (`prodsys.models.scenario_data.ScenarioData`)
        seed (int): Random seed for optimization.
        tabu_size (int): Size of the tabu list.
        max_steps (int): Maximum number of steps.
        max_score (int): Maximum score to stop optimization.
        number_of_seeds (int, optional): Number of seeds for optimization. Defaults to 1.
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

    hyper_parameters = TabuSearchHyperparameters(
        seed=seed, tabu_size=tabu_size, max_steps=max_steps, max_score=max_score, number_of_seeds=number_of_seeds
    )
    tabu_search_optimization(
        base_configuration=base_configuration,
        hyper_parameters=hyper_parameters,
        save_folder=save_folder,
        initial_solution=initial_solution,
        full_save=full_save,
    )


def tabu_search_optimization(
        base_configuration: adapters.ProductionSystemAdapter,
        hyper_parameters: TabuSearchHyperparameters,
        save_folder: str,
        initial_solution: adapters.ProductionSystemAdapter = None,
        full_save: bool = False,
):
    """
    Optimize a production system configuration using tabu search.

    Args:
        base_configuration (adapters.ProductionSystemAdapter): production system to optimize.
        hyper_parameters (SimulatedAnnealingHyperparameters): Hyperparameters for tabu search.
        save_folder (str): Folder to save the results in. Defaults to "results".
        initial_solution (adapters.ProductionSystemAdapter, optional): Initial solution for optimization. Defaults to None.
    """
    adapters.ProductionSystemAdapter.model_config["validate_assignment"] = False
    if not adapters.check_for_clean_compound_processes(base_configuration):
        logger.warning("Both compound processes and normal processes are used. This may lead to unexpected results.")
    if not check_breakdown_states_available(base_configuration):
        create_default_breakdown_states(base_configuration)

    set_seed(hyper_parameters.seed)

    weights = get_weights(base_configuration, "max")

    solution_dict = {
        "current_generation": "0", 
        "hashes": {} 
    }
    performances = {}
    performances["0"] = {}
    start = time.perf_counter()

    class Algorithm(TabuSearch):
        def _score(self, state):
            values = evaluate(
                base_scenario=base_configuration,
                performances=performances,
                solution_dict=solution_dict,
                number_of_seeds=hyper_parameters.number_of_seeds,
                full_save_folder_file_path=save_folder if full_save else "",
                individual=[state],
            )

            performance = sum(
                [value * weight for value, weight in zip(values, weights)]
            )
            counter = len(performances["0"]) - 1
            print(counter, performance)
            document_individual(solution_dict, save_folder, [state])

            performances["0"][state.ID] = {
                "agg_fitness": performance,
                "fitness": [float(value) for value in values],
                "time_stamp": time.perf_counter() - start,
                "hash": state.hash()
            }
            with open(f"{save_folder}/optimization_results.json", "w") as json_file:
                json.dump(performances, json_file)

            return performance

        def _neighborhood(self):
            neighboarhood = []
            for _ in range(10):
                while True:
                    configuration = mutation(individual=[deepcopy(self.current)])[0][0]
                    if check_valid_configuration(
                        configuration=configuration,
                        base_configuration=base_configuration,
                    ):
                        neighboarhood.append(configuration)
                        break
            return neighboarhood

    alg = Algorithm(
        initial_state=initial_solution,
        tabu_size=hyper_parameters.tabu_size,
        max_steps=hyper_parameters.max_steps,
        max_score=hyper_parameters.max_score,
    )
    best_solution, best_objective_value = alg.run()
    print(f"Best solution has ID {best_solution.ID} and objectives values: {best_objective_value}")



def optimize_configuration(
    base_configuration_file_path: str,
    scenario_file_path: str,
    save_folder: str,
    hyper_parameters: TabuSearchHyperparameters,
    full_save: bool = False,
):
    """
    Optimize configuration with tabu search.

    Args:
        base_configuration_file_path (str): File path of the serialized base configuration (`prodsys.adapters.JsonProductionSystemAdapter`)
        scenario_file_path (str): File path of the serialized scenario (`prodsys.models.scenario_data.ScenarioData`)
        save_folder (str): Folder to save the results in.
        hyper_parameters (TabuSearchHyperparameters): Hyperparameters for configuration optimization with tabu search.
    """
    run_tabu_search(
        save_folder=save_folder,
        base_configuration_file_path=base_configuration_file_path,
        scenario_file_path=scenario_file_path,
        seed=hyper_parameters.seed,
        tabu_size=hyper_parameters.tabu_size,
        max_steps=hyper_parameters.max_steps,
        max_score=hyper_parameters.max_score,
        number_of_seeds=hyper_parameters.number_of_seeds,
        full_save=full_save,
    )
