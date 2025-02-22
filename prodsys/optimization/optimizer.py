from __future__ import annotations
import json
import time

from typing import Any, Callable, Optional

import pandas as pd
from prodsys.adapters.json_adapter import JsonProductionSystemAdapter
from prodsys.optimization.optimization_data import (
    FitnessData,
    OptimizationProgress,
    OptimizationResults,
    OptimizationSolutions,
    SolutionMetadata,
    get_empty_optimization_results,
)
from prodsys.optimization.util import get_weights
from prodsys.simulation.runner import Runner
from prodsys.util import util

if util.run_from_ipython():
    from tqdm.notebook import tqdm
else:
    from tqdm import tqdm
from prodsys.adapters import ProductionSystemAdapter
from prodsys.optimization.evolutionary_algorithm import (
    EvolutionaryAlgorithmHyperparameters,
    evolutionary_algorithm_optimization,
)
from prodsys.optimization.math_opt import (
    MathOptHyperparameters,
    mathematical_optimization,
)
from prodsys.optimization.simulated_annealing import (
    SimulatedAnnealingHyperparameters,
    simulated_annealing_optimization,
)
from prodsys.optimization.tabu_search import (
    TabuSearchHyperparameters,
    tabu_search_optimization,
)

HyperParameters = (
    EvolutionaryAlgorithmHyperparameters
    | SimulatedAnnealingHyperparameters
    | TabuSearchHyperparameters
    | MathOptHyperparameters
)

class Optimizer:
    """
    The Optimizer allows to optimize the configuration of a production system. The optimization is based on the optimization scenario and, if available, a base configuration. For the optimization, different algorithms can be used and their hyperparameters can be adjusted.



    """

    def __init__(
        self,
        adapter: ProductionSystemAdapter,
        hyperparameters: HyperParameters,
        initial_solutions: list[ProductionSystemAdapter] = None,
        full_save: bool = False,
    ) -> None:
        self.adapter = adapter
        self.hyperparameters = hyperparameters
        self.initial_solutions = initial_solutions
        self.full_save = full_save

        self.configurations: list[ProductionSystemAdapter] = []
        self.weights = None
        self.pbar: Any = None

        self.optimization_cache_first_found_hashes = OptimizationSolutions()
        self.performances_cache: OptimizationResults = get_empty_optimization_results()

        self.progress = OptimizationProgress()

        self.start_time = None

    def get_algorithm_and_steps(self) -> tuple[Callable, int]:
        if isinstance(self.hyperparameters, EvolutionaryAlgorithmHyperparameters):
            updates = (
                self.hyperparameters.number_of_generations
                * self.hyperparameters.population_size
                + self.hyperparameters.population_size
            )
            self.weights = get_weights(self.adapter, "max")

            return evolutionary_algorithm_optimization, updates
        elif isinstance(self.hyperparameters, SimulatedAnnealingHyperparameters):
            updates = self.hyperparameters.steps
            self.weights = get_weights(self.adapter, "min")
            return simulated_annealing_optimization, updates
        elif isinstance(self.hyperparameters, TabuSearchHyperparameters):
            num_updates = (
                self.hyperparameters.max_steps * 10
            )  # Number of max_steps multiplied by 10 (Represent 10 neighbors in the search area as in function def _neighborhood()).
            self.weights = get_weights(self.adapter, "max")
            return tabu_search_optimization, num_updates
        elif isinstance(self.hyperparameters, MathOptHyperparameters):
            self.weights = get_weights(self.adapter, "min")
            return mathematical_optimization, 1
        else:
            raise ValueError("No algorithm provided for the optimization.")

    def optimize(self) -> ProductionSystemAdapter:
        """
        Optimizes the configuration of the production system based on the optimization scenario and the base configuration.

        Returns:
            ProductionSystemAdapter: The optimized configuration of the production system.
        """
        if not self.hyperparameters:
            raise ValueError("No hyperparameters provided for the optimizer.")
        if not self.adapter:
            raise ValueError("No adapter provided for the optimizer.")
        self.progress = OptimizationProgress()
        self.optimization_cache_first_found_hashes = OptimizationSolutions()
        self.performances_cache = get_empty_optimization_results()
        self.start_time = time.perf_counter()

        algorithm, steps = self.get_algorithm_and_steps()
        self.progress.total_steps = steps
        self.pbar = tqdm(total=steps, desc="Optimization Progress", leave=True)
        self.pbar.update(0)
        algorithm(self)
        self.pbar.close()

    def save_optimization_step(
        self,
        fitness_values: list[float],
        configuration: JsonProductionSystemAdapter,
        event_log_dict: dict = None
    ):
        """
        Saves the optimization step with the fitness values and the configuration.

        Args:
            fitness_values (list[float]): The fitness values of the optimization step.
            configuration (JsonProductionSystemAdapter): The configuration of the production system.
            event_log_dict (dict): The event log data of the configuration.
        """
        self.update_progress()
        fitness_data = self.get_fitness_data_entry(configuration, fitness_values, event_log_dict=event_log_dict)
        current_generation = self.optimization_cache_first_found_hashes.current_generation
        self.cache_fitness_data(fitness_data, current_generation)
        self.save_fitness_data(fitness_data, current_generation)

    def get_fitness_data_entry(
        self, configuration: JsonProductionSystemAdapter, fitness_values: list[float], event_log_dict: dict
    ) -> FitnessData:
        """
        Creates a FitnessData object from the configuration and fitness values.

        Args:
            configuration (JsonProductionSystemAdapter): The configuration of the production system.
            fitness_values (list[float]): The fitness values of the configuration.
            event_log_dict (dict): The event log data of the configuration.

        Returns:
            FitnessData: The fitness data of the configuration.
        """
        objective_names = [
            objective.name.value for objective in configuration.scenario_data.objectives
        ]
        agg_fitness = sum(
            [value * weight for value, weight in zip(fitness_values, self.weights)]
        )
        return FitnessData(
            agg_fitness=agg_fitness,
            fitness=fitness_values,
            time_stamp=time.perf_counter() - self.start_time,
            hash=configuration.hash(),
            production_system=configuration,
            objective_names=objective_names,
            event_log_dict=event_log_dict,
        )

    def cache_fitness_data(
        self,
        fitness_data: FitnessData,
        generation: str
    ) -> None:

        if not self.performances_cache.get(generation):
            self.performances_cache[generation] = {}

        configuration = fitness_data.production_system
        if (
            fitness_data.production_system.hash()
            not in self.optimization_cache_first_found_hashes.hashes
        ):
            self.optimization_cache_first_found_hashes.hashes[
                configuration.hash()
            ] = SolutionMetadata(generation=generation, ID=configuration.ID)

        self.performances_cache[generation][configuration.ID] = fitness_data

    def save_fitness_data(self, fitness_data: FitnessData, generation: str) -> None:
        """
        Saves the configuration of the production system.

        Args:
            configuration (JsonProductionSystemAdapter): The configuration of the production system.
        """
        raise NotImplementedError("Method save_configuration not implemented.")

    def get_optimization_results(self) -> OptimizationResults:
        """
        Retrieves the optimization results of the production system.

        Returns:
            OptimizationResults: The optimization results of the production system.
        """
        if self.performances_cache:
            return self.performances_cache
        else:
            return self.get_optimization_results_from_persistence()

    def get_optimization_result_configuration(
            self, solution_id: str
        ) -> JsonProductionSystemAdapter:
        """
        Retrieves the configuration of the production system.

        Args:
            solution_id (str): The ID of the solution.

        Returns:
            JsonProductionSystemAdapter: The configuration of the production system.
        """
        optimization_results = self.get_optimization_results()
        for generation in optimization_results:
            for adapter_id, fitness_data in optimization_results[generation].items():
                if adapter_id == solution_id:
                    return fitness_data.production_system

        raise ValueError(f"Solution {solution_id} not found in optimization results.")

    def get_optimization_results_from_persistence(
        self, configuration_data: bool = False, event_log_data: bool = False
    ) -> OptimizationResults:
        """
        Retrieves the optimization results of the production system.

        Returns:
            OptimizationResults: The optimization results of the production system.
        """
        raise NotImplementedError("Method get_optimization_results from persistence not implemented.")

    def get_fitness_data(self, generation: str, adapter_id: str) -> FitnessData:
        """
        Retrieves the optimization result of the production system.

        Args:
            generation (str): The generation of the optimization result.
            adapter_id (str): The ID of the adapter.

        Returns:
            FitnessData: The optimization result of the production system.
        """
        try:
            return self.get_fitness_data_from_cache(generation, adapter_id)
        except:
            return self.get_fitness_data_from_persistence(generation, adapter_id)

    def get_configuration(
        self, generation: str, adapter_id: str
    ) -> JsonProductionSystemAdapter:
        """
        Retrieves the configuration of the production system.

        Args:
            generation (str): The generation of the configuration.
            adapter_id (str): The ID of the adapter.

        Returns:
            JsonProductionSystemAdapter: The configuration of the production system.
        """
        fitness_data = self.get_fitness_data(generation, adapter_id)
        return fitness_data.production_system

    def get_fitness_data_from_cache(
        self, generation: str, adapter_id: str
    ) -> FitnessData:
        """
        Retrieves the optimization result of the production system.

        Args:
            generation (str): The generation of the optimization result.
            adapter_id (str): The ID of the adapter.

        Returns:
            FitnessData: The optimization result of the production system.

        Raises:
            ValueError: If the optimization result is not found in the cache.
        """
        if not generation in self.performances_cache or not adapter_id in self.performances_cache[generation]:
            raise ValueError("Optimization result not found in cache.")
        return self.performances_cache[generation][adapter_id]

    def get_fitness_data_from_persistence(
        self, generation: str, adapter_id: str
    ) -> FitnessData:
        """
        Retrieves the optimization result of the production system.

        Args:
            generation (str): The generation of the optimization result.
            adapter_id (str): The ID of the adapter.

        Returns:
            FitnessData: The optimization result of the production system.
        """
        raise NotImplementedError("Method get_optimization_result from persistence not implemented.")

    def update_progress(self, num_steps: int = 1) -> None:
        """
        Updates the progress bar of the optimizer.

        Args:
            steps (int, optional): Number of steps to update the progress bar. Defaults to 1.
        """
        # TODO: consider best performance or so in the progress bar
        if self.pbar:
            self.pbar.update(num_steps)
            self.progress.completed_steps += num_steps
        else:
            raise ValueError("Progress bar not initialized.")

    def get_progress(self) -> OptimizationProgress:
        return self.progress

    def save_solutions(self) -> None:
        """
        Saves the solutions of the optimizer.
        """
        pass

    def save_performance(self) -> None:
        """
        Saves the performance of the optimizer.
        """
        pass


class FileSystemSaveOptimizer(Optimizer):
    def __init__(
        self,
        adapter: ProductionSystemAdapter,
        hyperparameters: HyperParameters,
        save_folder: str,
        initial_solutions: list[ProductionSystemAdapter] = None,
        full_save: bool = False,
    ) -> None:
        super().__init__(adapter, hyperparameters, initial_solutions, full_save)
        self.save_folder = save_folder

    def save_fitness_data(
        self, fitness_data: FitnessData, generation: str
    ) -> None:
        """
        Saves the configuration of the production system to the file system.

        Args:
            configuration (JsonProductionSystemAdapter): The configuration of the production system.
        """
        # save also the optimization results and overwrite current status

        # salve also the dict event log as json file in the same folder (only done with the hash to save memory)
        df = pd.DataFrame.from_dict(fitness_data.event_log_dict)
        df.to_json(f"{self.save_folder}/event_log_dict_{fitness_data.hash}.json", indent=4)

        # save configuraion
        JsonProductionSystemAdapter.model_validate(fitness_data.production_system).write_data(
            f"{self.save_folder}/generation_{str(generation)}_{fitness_data.production_system.ID}.json"
        )

        # save configuratino per hash
        JsonProductionSystemAdapter.model_validate(fitness_data.production_system).write_data(
            f"{self.save_folder}/hash_{fitness_data.hash}.json"
        )

        # Save optimization results (the fitness data dict, but with no adapter in prodcution_system variable and no event logs)
        optimization_results = {}
        for generation in self.performances_cache:
            if not generation in optimization_results:
                optimization_results[generation] = {}
            for adapter_id, fitness_data in self.performances_cache[generation].items():
                optimization_results[generation][adapter_id] = fitness_data.model_dump(
                    exclude={"production_system", "event_log_dict"}
                )

        with open(f"{self.save_folder}/optimization_results.json", "w") as json_file:
            json.dump(optimization_results, json_file)


    def get_fitness_data_from_persistence(
        self, generation: str, adapter_id: str
    ) -> FitnessData:
        """
        Retrieves the optimization result of the production system from the file system.

        Args:
            generation (str): The generation of the optimization result.
            adapter_id (str): The ID of the adapter.
        
        Returns:
            FitnessData: The optimization result of the production system.
        """
        with open(f"{self.save_folder}/optimization_results.json", "r") as json_file:
            optimization_results = json.load(json_file)
        fitness_data_dict = optimization_results[generation][adapter_id]
        fitness_data = FitnessData.model_validate(fitness_data_dict)

        fitness_data.production_system = JsonProductionSystemAdapter().read_data(
            f"{self.save_folder}/hash_{fitness_data.hash}.json"
        )

        df = pd.read_json(f"{self.save_folder}/event_log_dict_{fitness_data.hash}.json")
        fitness_data.event_log_dict = df.to_dict()
        return fitness_data
    

    def get_optimization_results_from_persistence(
        self, configuration_data: bool = False, event_log_data: bool = False
    ) -> OptimizationResults:
        """
        Retrieves the optimization results of the production system from the file system.

        Returns:
            OptimizationResults: The optimization results of the production system.
        """
        with open(f"{self.save_folder}/optimization_results.json", "r") as json_file:
            optimization_results: OptimizationResults = json.load(json_file)
        if configuration_data:
            for generation in optimization_results:
                for adapter_id, fitness_data in optimization_results[generation].items():
                    fitness_data.production_system = JsonProductionSystemAdapter().read_data(
                        f"{self.save_folder}/hash_{fitness_data.hash}.json"
                    )
        if event_log_data:
            for generation in optimization_results:
                for adapter_id, fitness_data in optimization_results[generation].items():
                    df = pd.read_json(f"{self.save_folder}/event_log_dict_{fitness_data.hash}.json")
                    fitness_data.event_log_dict = df.to_dict()
        return optimization_results
