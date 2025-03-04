from __future__ import annotations
from abc import ABC, abstractmethod
import json
import time
from typing import Any, Callable, Optional

import pandas as pd
from pydantic import TypeAdapter
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


class Optimizer(ABC):
    """
    Base Optimizer interface for optimizing the configuration of a production system.
    This class defines the common interface and shared logic for optimization but cannot be used directly.
    """

    def __init__(
        self,
        adapter: ProductionSystemAdapter,
        hyperparameters: HyperParameters,
        initial_solutions: Optional[list[ProductionSystemAdapter]] = None,
        full_save: bool = False,
    ) -> None:
        self.adapter = adapter
        self.hyperparameters = hyperparameters
        self.initial_solutions = initial_solutions
        self.full_save = full_save  # Determines whether event logs are saved

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
            updates = self.hyperparameters.max_steps * 10  # 10 neighbors per step
            self.weights = get_weights(self.adapter, "max")
            return tabu_search_optimization, updates
        elif isinstance(self.hyperparameters, MathOptHyperparameters):
            self.weights = get_weights(self.adapter, "min")
            return mathematical_optimization, 1
        else:
            raise ValueError("No algorithm provided for the optimization.")

    def optimize(self):
        """
        Performs the optimization process.
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
        event_log_dict: Optional[dict] = None,
    ) -> None:
        """
        Save an optimization step, caching and persisting the fitness data.
        """
        self.update_progress()
        fitness_data = self.get_fitness_data_entry(
            configuration, fitness_values, event_log_dict=event_log_dict
        )
        current_generation = (
            self.optimization_cache_first_found_hashes.current_generation
        )
        self.cache_fitness_data(fitness_data, current_generation)
        self.save_fitness_data(fitness_data, current_generation)

    def get_fitness_data_entry(
        self,
        configuration: JsonProductionSystemAdapter,
        fitness_values: list[float],
        event_log_dict: Optional[dict],
    ) -> FitnessData:
        """
        Creates and returns a FitnessData entry for a given configuration.
        """
        objective_names = [
            obj.name.value for obj in configuration.scenario_data.objectives
        ]
        agg_fitness = sum(
            value * weight for value, weight in zip(fitness_values, self.weights)
        )
        return FitnessData(
            agg_fitness=agg_fitness,
            fitness=fitness_values,
            time_stamp=time.perf_counter() - self.start_time,
            hash=configuration.hash(),
            production_system=configuration,
            objective_names=objective_names,
            event_log_dict=event_log_dict if self.full_save else None,
        )

    def cache_fitness_data(self, fitness_data: FitnessData, generation: str) -> None:
        """
        Caches the fitness data in memory.
        """
        if generation not in self.performances_cache:
            self.performances_cache[generation] = {}
        configuration = fitness_data.production_system
        if (
            configuration.hash()
            not in self.optimization_cache_first_found_hashes.hashes
        ):
            self.optimization_cache_first_found_hashes.hashes[configuration.hash()] = (
                SolutionMetadata(generation=generation, ID=configuration.ID)
            )
        self.performances_cache[generation][configuration.ID] = fitness_data

    @abstractmethod
    def save_fitness_data(self, fitness_data: FitnessData, generation: str) -> None:
        """
        Persists the fitness data. Must be implemented by concrete subclasses.
        """
        ...

    def get_optimization_results(
        self, configuration_data: bool = True, event_log_data: bool = False
    ) -> OptimizationResults:
        """
        Retrieves the optimization results. If the cache is non-empty, it is returned.
        Otherwise, data is loaded from persistence.

        Flags:
         - configuration_data: load full configuration data if available. Default is True.
         - event_log_data: load the event log details if available. Default is False.
        """
        if self.performances_cache and not event_log_data:
            if configuration_data and event_log_data == self.full_save:
                return self.performances_cache
            results = {}
            for generation, fitness_data in self.performances_cache.items():
                results[generation] = {}
                for adapter_id, fitness_data_entry in fitness_data.items():
                    copied_fitness_data = fitness_data_entry.model_copy(deep=True)
                    if not configuration_data:
                        copied_fitness_data.production_system = None
                    if not event_log_data:
                        copied_fitness_data.event_log_dict = None
                    results[generation][adapter_id] = copied_fitness_data
        else:
            results = self.get_optimization_results_from_persistence(
                configuration_data, event_log_data
            )
        return results

    def get_optimization_result_configuration(
        self, solution_id: str
    ) -> JsonProductionSystemAdapter:
        """
        Returns the configuration of the solution identified by solution_id.
        """
        optimization_results = self.get_optimization_results()
        for generation in optimization_results:
            for adapter_id, fitness_data in optimization_results[generation].items():
                if adapter_id == solution_id:
                    return fitness_data.production_system
        raise ValueError(f"Solution {solution_id} not found in optimization results.")

    @abstractmethod
    def get_optimization_results_from_persistence(
        self, configuration_data: bool = False, event_log_data: bool = False
    ) -> OptimizationResults:
        """
        Retrieves optimization results from persistence (e.g. file system).
        Must be implemented by concrete subclasses.
        """
        ...

    def get_fitness_data(self, generation: str, adapter_id: str) -> FitnessData:
        """
        Returns the fitness data for a given generation and adapter_id.
        """
        try:
            return self.get_fitness_data_from_cache(generation, adapter_id)
        except Exception:
            return self.get_fitness_data_from_persistence(generation, adapter_id)

    def get_fitness_data_from_cache(
        self, generation: str, adapter_id: str
    ) -> FitnessData:
        if (
            generation not in self.performances_cache
            or adapter_id not in self.performances_cache[generation]
        ):
            raise ValueError("Optimization result not found in cache.")
        return self.performances_cache[generation][adapter_id]

    @abstractmethod
    def get_fitness_data_from_persistence(
        self, generation: str, adapter_id: str
    ) -> FitnessData:
        """
        Retrieves fitness data from persistence. Must be implemented by concrete subclasses.
        """
        ...

    def update_progress(self, num_steps: int = 1) -> None:
        """
        Updates the progress bar.
        """
        if self.pbar:
            self.pbar.update(num_steps)
            self.progress.completed_steps += num_steps
        else:
            raise ValueError("Progress bar not initialized.")

    def get_progress(self) -> OptimizationProgress:
        return self.progress


class InMemoryOptimizer(Optimizer):
    """
    Optimizer implementation that holds all data in memory (cache).
    No persistence is performed.
    """

    def save_fitness_data(self, fitness_data: FitnessData, generation: str) -> None:
        # In-memory optimizer only caches data, so no additional action is needed.
        pass

    def get_optimization_results_from_persistence(
        self, configuration_data: bool = False, event_log_data: bool = False
    ) -> OptimizationResults:
        # Since all data is in memory, simply return the cache.
        return self.performances_cache

    def get_fitness_data_from_persistence(
        self, generation: str, adapter_id: str
    ) -> FitnessData:
        raise NotImplementedError(
            "Method get_fitness_data_from_persistence not implemented in InMemoryOptimizer. Make sure optimization run was conducted and use get_fitness_data instead."
        )


class FileSystemSaveOptimizer(Optimizer):
    """
    Optimizer implementation that saves data to the file system.

    Args:
        adapter (ProductionSystemAdapter): The production system adapter to optimize.
        hyperparameters (HyperParameters): The hyperparameters for the optimization.
        save_folder (str): The folder where data will be saved.
        initial_solutions (Optional[list[ProductionSystemAdapter]], optional): Initial solutions to start the optimization. Defaults to None.
        full_save (bool, optional): Whether to save full event log data. Defaults to False.
        caching (bool, optional): Whether to cache results in memory. Defaults to True.
    """

    def __init__(
        self,
        adapter: ProductionSystemAdapter,
        hyperparameters: HyperParameters,
        save_folder: str,
        initial_solutions: Optional[list[ProductionSystemAdapter]] = None,
        full_save: bool = False,
    ) -> None:
        super().__init__(adapter, hyperparameters, initial_solutions, full_save)
        self.save_folder = save_folder
        util.prepare_save_folder(self.save_folder + "/")

    def save_fitness_data(self, fitness_data: FitnessData, generation: str) -> None:
        """
        Saves the fitness data to disk.
        If full_save is True, event log data is also persisted.
        """
        if self.full_save and fitness_data.event_log_dict:
            df = pd.DataFrame.from_dict(fitness_data.event_log_dict)
            df.to_json(
                f"{self.save_folder}/event_log_dict_{fitness_data.hash}.json", indent=4
            )
            fitness_data.event_log_dict = None # Free up memory
        JsonProductionSystemAdapter.model_validate(
            fitness_data.production_system
        ).write_data(
            f"{self.save_folder}/generation_{generation}_{fitness_data.production_system.ID}.json"
        )
        JsonProductionSystemAdapter.model_validate(
            fitness_data.production_system
        ).write_data(f"{self.save_folder}/hash_{fitness_data.hash}.json")
        # Update the aggregated optimization results on disk.
        optimization_results = {}
        for gen in self.performances_cache:
            if gen not in optimization_results:
                optimization_results[gen] = {}
            for adapter_id, fitness_data_entry in self.performances_cache[gen].items():
                optimization_results[gen][adapter_id] = fitness_data_entry.model_dump(
                    exclude={"production_system", "event_log_dict"}
                )
        with open(f"{self.save_folder}/optimization_results.json", "w") as json_file:
            json.dump(optimization_results, json_file, indent=4)

    def get_fitness_data_from_persistence(
        self, generation: str, adapter_id: str
    ) -> FitnessData:
        """
        Loads the fitness data for a given generation and adapter_id from disk.
        """
        with open(f"{self.save_folder}/optimization_results.json", "r") as json_file:
            optimization_results = json.load(json_file)
        fitness_data_dict = optimization_results[generation][adapter_id]
        fitness_data = FitnessData.model_validate(fitness_data_dict)
        fitness_data.production_system = JsonProductionSystemAdapter().read_data(
            f"{self.save_folder}/hash_{fitness_data.hash}.json"
        )
        if self.full_save:
            df = pd.read_json(
                f"{self.save_folder}/event_log_dict_{fitness_data.hash}.json"
            )
            fitness_data.event_log_dict = df.to_dict()
        else:
            fitness_data.event_log_dict = None
        return fitness_data

    def get_optimization_results_from_persistence(
        self, configuration_data: bool = False, event_log_data: bool = False
    ) -> OptimizationResults:
        """
        Loads the entire optimization results from disk.
        The flags determine if full configuration data and/or event log data are included.
        """
        with open(f"{self.save_folder}/optimization_results.json", "r") as json_file:
            optimization_results_data = json.load(json_file)
        optimization_results: OptimizationResults = TypeAdapter(
            OptimizationResults
        ).validate_python(optimization_results_data)
        if configuration_data:
            for generation in optimization_results:
                for adapter_id, fitness_data in optimization_results[
                    generation
                ].items():
                    production_system = JsonProductionSystemAdapter()
                    production_system.read_data(
                        f"{self.save_folder}/hash_{fitness_data.hash}.json"
                    )
                    production_system.ID = adapter_id
                    fitness_data.production_system = production_system
        if event_log_data and self.full_save:
            for generation in optimization_results:
                for adapter_id, fitness_data in optimization_results[
                    generation
                ].items():
                    df = pd.read_json(
                        f"{self.save_folder}/event_log_dict_{fitness_data.hash}.json"
                    )
                    fitness_data.event_log_dict = df.to_dict()
        return optimization_results
