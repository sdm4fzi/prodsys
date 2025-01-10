from __future__ import annotations
import time

from typing import Any, Callable, Optional
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
from prodsys.optimization.math_opt import MathOptHyperparameters, mathematical_optimization
from prodsys.optimization.simulated_annealing import SimulatedAnnealingHyperparameters, simulated_annealing_optimization
from prodsys.optimization.tabu_search import TabuSearchHyperparameters, tabu_search_optimization

HyperParameters = EvolutionaryAlgorithmHyperparameters | SimulatedAnnealingHyperparameters | TabuSearchHyperparameters | MathOptHyperparameters


class Optimizer:
    """
    The Optimizer allows to optimize the configuration of a production system. The optimization is based on the optimization scenario and, if available, a base configuration. For the optimization, different algorithms can be used and their hyperparameters can be adjusted.



    """

    def __init__(self, adapter: ProductionSystemAdapter, hyperparameters: HyperParameters, initial_solutions: list[ProductionSystemAdapter] = None, save_folder: Optional[str] = None, full_save: bool = False) -> None:
        self.adapter = adapter
        self.hyperparameters = hyperparameters
        self.initial_solutions = initial_solutions
        self.save_folder = save_folder
        self.full_save = full_save

        self.configurations: list[ProductionSystemAdapter] = []
        self.pbar: Any = None

        self.solutions_dict = {"current_generation": "0", "hashes": {}}
        self.performances = {"0": {}}

        self.progress = {
            "total_steps": 0,
            "completed_steps": 0, 
            "hashes": {},
        }

        self.start_time = None

    def get_algorithm_and_steps(self) -> tuple[Callable, int]:
        if isinstance(self.hyperparameters, EvolutionaryAlgorithmHyperparameters):
            updates = self.hyperparameters.number_of_generations * self.hyperparameters.population_size + self.hyperparameters.population_size
            return evolutionary_algorithm_optimization, updates
        elif isinstance(self.hyperparameters, SimulatedAnnealingHyperparameters):
            updates = self.hyperparameters.steps
            return simulated_annealing_optimization, updates
        elif isinstance(self.hyperparameters, TabuSearchHyperparameters):
            num_updates = self.hyperparameters.max_steps
            return tabu_search_optimization, num_updates
        elif isinstance(self.hyperparameters, MathOptHyperparameters):
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
        # TODO: reset performance and solutions dict when starting a new optimization
        self.start_time = time.time()
        
        algorithm, steps = self.get_algorithm_and_steps()
        self.progress["total_steps"] = steps
        self.pbar = tqdm(total=steps, desc="Optimization Progress", leave=True)
        self.pbar.update(0)
        algorithm(self)
        self.pbar.close()
        print("Optimization runs are finished.")

    def update_progress(self, num_steps: int = 1) -> None:
        """
        Updates the progress bar of the optimizer.

        Args:
            steps (int, optional): Number of steps to update the progress bar. Defaults to 1.
        """
        # TODO: maybe also consider best performance or so in the progress bar
        # TODO: also test if this is working for all algorithms that 100% is reached exactly
        if self.pbar:
            self.pbar.update(num_steps)
            self.progress["completed_steps"] += num_steps
        else:
            raise ValueError("Progress bar not initialized.")

    def get_progress(self) -> dict:
        return {
            "total_steps": self.progress["total_steps"],
            "completed_steps": self.progress["completed_steps"],
        }


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

