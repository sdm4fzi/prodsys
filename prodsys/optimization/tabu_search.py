from abc import ABCMeta, abstractmethod
from copy import deepcopy
from collections import deque
from numpy import argmax

import logging

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prodsys.optimization.optimizer import Optimizer

from prodsys.optimization.optimization import evaluate
from prodsys.optimization.adapter_manipulation import mutation
from prodsys.optimization.optimization import check_valid_configuration

# from prodsys.optimization.util import document_individual


from pydantic import BaseModel, ConfigDict

from prodsys import adapters
from prodsys.optimization.util import (
    check_breakdown_states_available,
    create_default_breakdown_states,
)
from prodsys.util.util import set_seed

logger = logging.getLogger(__name__)


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

            neighborhood = self._neighborhood()
            neighborhood_best = self._best(neighborhood)

            while True:
                if all([x in self.tabu_list for x in neighborhood]):
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
                return self.best, self._score(self.best)
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
    neighborhood_size: int = 10
    max_score: float = 500
    number_of_seeds: int = 1

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "seed": 0,
                    "tabu_size": 10,
                    "max_steps": 300,
                    "neighborhood_size": 10,
                    "max_score": 500,
                    "number_of_seeds": 1,
                },
            ]
        },
        extra="forbid",
    )


def tabu_search_optimization(
    optimizer: "Optimizer",
):
    """
    Optimize a production system configuration using tabu search.

    Args:
        optimizer (Optimizer): The optimizer that contains the adapter, hyperparameters for tabu search, and initial solution (Defaults to None).
    """
    adapters.ProductionSystemData.model_config["validate_assignment"] = False

    base_configuration = optimizer.adapter.model_copy(deep=True)
    if not adapters.check_for_clean_compound_processes(base_configuration):
        logger.warning(
            "Both compound processes and normal processes are used. This may lead to unexpected results."
        )
    if not check_breakdown_states_available(base_configuration):
        create_default_breakdown_states(base_configuration)

    hyper_parameters: TabuSearchHyperparameters = optimizer.hyperparameters
    set_seed(hyper_parameters.seed)

    solution_dict = optimizer.optimization_cache_first_found_hashes

    class Algorithm(TabuSearch):

        def __init__(
            self,
            optimizer: "Optimizer",
            initial_state,
            tabu_size,
            max_steps,
            neighborhood_size,
            max_score=None,
        ):
            super().__init__(initial_state, tabu_size, max_steps, max_score)
            self.optimizer = optimizer
            self.previous_counter = None
            self.neighborhood_size = neighborhood_size

        def _score(self, state):
            fitness_values, event_log_dict = evaluate(
                base_scenario=base_configuration,
                solution_dict=solution_dict,
                number_of_seeds=hyper_parameters.number_of_seeds,
                adapter_object=state,
                full_save=optimizer.full_save,
            )

            fitness_values, event_log_dict = self.optimizer.save_optimization_step(
                fitness_values=fitness_values,
                configuration=state,
                event_log_dict=event_log_dict,
            )
            performance = sum(
                [
                    value * weight
                    for value, weight in zip(fitness_values, self.optimizer.weights)
                ]
            )
            return performance

        def _neighborhood(self):
            neighboarhood = []
            for _ in range(self.neighborhood_size):
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
        optimizer=optimizer,
        initial_state=optimizer.initial_solutions,
        tabu_size=hyper_parameters.tabu_size,
        max_steps=hyper_parameters.max_steps,
        max_score=hyper_parameters.max_score,
        neighborhood_size=hyper_parameters.neighborhood_size,
    )
    best_solution, best_objective_value = alg.run()
    optimizer.update_progress(
        num_steps=optimizer.progress.total_steps - optimizer.progress.completed_steps
    )
