"""
Capacity-based optimization algorithm.

This module provides a simple but effective optimization approach that generates
random configurations based on capacity analysis and selects the best performing ones.
It's particularly useful for fast optimization runs and initial solution generation.
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, ConfigDict
from prodsys.optimization.adapter_manipulation import (
    configuration_capacity_based_asserted,
)
from prodsys.optimization.optimization import evaluate
from prodsys.util.util import run_from_ipython

if run_from_ipython():
    from multiprocessing.pool import ThreadPool as Pool
else:
    from multiprocessing.pool import Pool

if TYPE_CHECKING:
    from prodsys.optimization.optimizer import Optimizer


class CapacityBasedHyperparameters(BaseModel):
    """
    Hyperparameters for capacity-based optimization.
    
    Args:
        num_solutions (int): Number of random solutions to generate and evaluate.
        cap_target (float): Target capacity utilization for resources (0.0 to 1.0).
                           Default is 0.65 (65% utilization).
        seed (int): Random seed for reproducibility. Default is 0.
        number_of_seeds (int): Number of simulation seeds to run per configuration.
                              Default is 1.
        number_of_processes (int): Number of processes to use for parallelization.
                                  Default is 1 (no parallelization).
    """
    num_solutions: int = Field(100, description="Number of solutions to generate and evaluate")
    cap_target: float = Field(0.65, description="Target capacity utilization (0.0-1.0)", ge=0.0, le=1.0)
    seed: int = Field(0, description="Random seed for reproducibility")
    number_of_seeds: int = Field(1, description="Number of simulation seeds per configuration")
    number_of_processes: int = Field(1, description="Number of processes for parallel execution")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "num_solutions": 100,
                    "cap_target": 0.65,
                    "seed": 0,
                    "number_of_seeds": 1,
                    "number_of_processes": 4,
                },
            ]
        },
        extra="forbid",
    )


def _evaluate_configuration(args):
    """
    Wrapper function for parallel evaluation of configurations.
    
    Args:
        args: Tuple of (base_configuration, solution_dict, number_of_seeds, configuration, full_save)
    
    Returns:
        Tuple of (configuration, fitness_values, event_log_dict)
    """
    base_configuration, solution_dict, number_of_seeds, configuration, full_save = args
    fitness_values, event_log_dict = evaluate(
        base_scenario=base_configuration,
        solution_dict=solution_dict,
        number_of_seeds=number_of_seeds,
        adapter_object=configuration,
        full_save=full_save,
    )
    return configuration, fitness_values, event_log_dict


def capacity_based_optimization(optimizer: Optimizer) -> None:
    """
    Performs capacity-based optimization by generating random configurations
    based on capacity analysis and selecting the best performers.
    
    This is a simple but effective approach that:
    1. Generates N random configurations using capacity-based logic
    2. Evaluates each configuration via simulation (in parallel if specified)
    3. Returns the best configurations found
    
    The capacity-based generation ensures configurations are feasible and
    respect resource constraints while targeting specific utilization levels.
    
    Args:
        optimizer (Optimizer): The optimizer instance containing the base configuration
                              and hyperparameters.
    """
    hyperparameters: CapacityBasedHyperparameters = optimizer.hyperparameters
    base_configuration = optimizer.adapter
    
    logging.info(
        f"Starting capacity-based optimization with {hyperparameters.num_solutions} "
        f"solutions, cap_target={hyperparameters.cap_target}, "
        f"processes={hyperparameters.number_of_processes}"
    )
    
    # Set the generation identifier for tracking
    optimizer.optimization_cache_first_found_hashes.current_generation = "capacity_based"
    
    # PHASE 1: Generate all configurations
    logging.info("Generating configurations...")
    configurations = []
    generation_failures = 0
    
    for i in range(hyperparameters.num_solutions):
        try:
            configuration = configuration_capacity_based_asserted(
                baseline=base_configuration,
                cap_target=hyperparameters.cap_target
            )
            configurations.append(configuration)
        except Exception as e:
            generation_failures += 1
            logging.warning(
                f"Failed to generate configuration {i+1}/{hyperparameters.num_solutions}: {e}"
            )
            
            # If too many generation failures, stop early
            if generation_failures > hyperparameters.num_solutions * 0.5:
                logging.error(
                    f"More than 50% of configurations failed to generate ({generation_failures}/{i+1}). "
                    "Stopping optimization. Check configuration constraints."
                )
                break
    
    if not configurations:
        logging.error("No valid configurations were generated. Optimization aborted.")
        return
    
    logging.info(f"Generated {len(configurations)} valid configurations (failed: {generation_failures})")
    
    # PHASE 2: Evaluate all configurations (in parallel if specified)
    logging.info("Evaluating configurations...")
    
    # Prepare arguments for evaluation
    eval_args = [
        (
            base_configuration,
            optimizer.optimization_cache_first_found_hashes,
            hyperparameters.number_of_seeds,
            config,
            optimizer.full_save
        )
        for config in configurations
    ]
    
    # Execute evaluations (parallel or sequential)
    if hyperparameters.number_of_processes > 1:
        with Pool(hyperparameters.number_of_processes) as pool:
            results = pool.map(_evaluate_configuration, eval_args)
    else:
        results = [_evaluate_configuration(args) for args in eval_args]
    
    # PHASE 3: Save results
    solutions_evaluated = 0
    evaluation_failures = 0
    
    for configuration, fitness_values, event_log_dict in results:
        try:
            # Check if evaluation was successful (fitness_values would be None if cached or invalid)
            if fitness_values is None:
                # Configuration was either cached or invalid - still save it
                pass
            
            optimizer.save_optimization_step(
                fitness_values=fitness_values,
                configuration=configuration,
                event_log_dict=event_log_dict,
            )
            solutions_evaluated += 1
            
        except Exception as e:
            evaluation_failures += 1
            logging.warning(f"Failed to save evaluation result: {e}")
    
    logging.info(
        f"Capacity-based optimization completed. "
        f"Generated: {len(configurations)}, "
        f"Evaluated: {solutions_evaluated}, "
        f"Generation failures: {generation_failures}, "
        f"Evaluation failures: {evaluation_failures}"
    )

