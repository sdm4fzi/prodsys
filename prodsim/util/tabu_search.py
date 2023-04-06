from abc import ABCMeta, abstractmethod
from copy import deepcopy
from random import randint, random, shuffle
from collections import deque
from numpy import argmax

import json
import time

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


class TabuSearch:
    """
    Conducts tabu search
    """
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
        """

        :param initial_state: initial state, should implement __eq__ or __cmp__
        :param tabu_size: number of states to keep in tabu list
        :param max_steps: maximum number of steps to run algorithm for
        :param max_score: score to stop algorithm once reached
        """
        self.initial_state = initial_state

        if isinstance(tabu_size, int) and tabu_size > 0:
            self.tabu_size = tabu_size
        else:
            raise TypeError('Tabu size must be a positive integer')

        if isinstance(max_steps, int) and max_steps > 0:
            self.max_steps = max_steps
        else:
            raise TypeError('Maximum steps must be a positive integer')

        if max_score is not None:
            if isinstance(max_score, (int, float)):
                self.max_score = float(max_score)
            else:
                raise TypeError('Maximum score must be a numeric type')

    def __str__(self):
        return ('TABU SEARCH: \n' +
                'CURRENT STEPS: %d \n' +
                'BEST SCORE: %f \n' +
                'BEST MEMBER: %s \n\n') % \
               (self.cur_steps, self._score(self.best), str(self.best))

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
        """
        Returns objective function value of a state

        :param state: a state
        :return: objective function value of state
        """
        pass

    @abstractmethod
    def _neighborhood(self):
        """
        Returns list of all members of neighborhood of current state, given self.current

        :return: list of members of neighborhood
        """
        pass

    def _best(self, neighborhood):
        """
        Finds the best member of a neighborhood

        :param neighborhood: a neighborhood
        :return: best member of neighborhood
        """
        return neighborhood[argmax([self._score(x) for x in neighborhood])]

    def run(self, verbose=True):
        """
        Conducts tabu search

        :param verbose: indicates whether or not to print progress regularly
        :return: best state and objective function value of best state
        """
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
    

def run_tabu_search(
    save_folder: str,
    base_configuration_file_path: str,
    scenario_file_path: str,
    seed: int,
    tabu_size,
    max_steps,
    max_score,
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

    weights = get_weights(base_configuration, "max")

    solution_dict = {"current_generation": "0", "0": []}
    performances = {}
    performances["0"] = {}
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
            counter = len(performances["0"]) - 1
            print(counter, performance)
            document_individual(solution_dict, save_folder, [state])

            performances["0"][str(counter)] = {
                "agg_fitness": performance,
                "fitness": [float(value) for value in values],
                "time_stamp": time.perf_counter() - start,
            }
            with open(f"{save_folder}/optimization_results.json", "w") as json_file:
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
        
    alg = Algorithm(initial_state=initial_solution, tabu_size=tabu_size,
                    max_steps=max_steps, max_score=max_score)
    best_solution, best_objective_value = alg.run()
    print("Best solution: ", best_objective_value)