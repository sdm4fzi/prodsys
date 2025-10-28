"""
Example of capacity-based optimization.

This example demonstrates how to use the capacity-based optimization algorithm
to quickly generate and evaluate configurations based on capacity analysis.

This approach is particularly useful for:
- Fast optimization runs
- Initial solution generation
- Exploring the solution space efficiently
- Baseline comparisons
"""

import datetime
from prodsys.models.production_system_data import ProductionSystemData
from prodsys.optimization.capacity_based_optimization import (
    CapacityBasedHyperparameters,
)
from prodsys.optimization.optimizer import FileSystemSaveOptimizer


def main():
    # Define hyperparameters for capacity-based optimization
    hyper_parameters = CapacityBasedHyperparameters(
        num_solutions=50,          # Generate and evaluate 50 solutions
        cap_target=0.65,           # Target 65% capacity utilization
        seed=42,                   # Random seed for reproducibility
        number_of_seeds=1,         # Run 2 simulation seeds per configuration
        number_of_processes=4,     # Use 4 parallel processes (set to 1 for sequential)
    )

    # Load the base configuration
    base_configuration = ProductionSystemData.read(
        "examples/optimization/optimization_example/base_scenario.json",
    )
    base_configuration.read_scenario(
        "examples/optimization/optimization_example/scenario.json",
    )

    # Create optimizer with file system persistence
    optimizer = FileSystemSaveOptimizer(
        adapter=base_configuration,
        hyperparameters=hyper_parameters,
        save_folder=f"data/capacity_opt_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}",
        full_save=False,  # Set to True to save event logs
    )

    # Run the optimization
    print(f"Starting capacity-based optimization with {hyper_parameters.num_solutions} solutions...")
    print(f"Target capacity utilization: {hyper_parameters.cap_target * 100:.1f}%")
    
    optimizer.optimize()
    
    print("\nOptimization completed!")
    
    # Get results
    results = optimizer.get_optimization_results(configuration_data=False)
    
    # Find best solution
    best_fitness = float('-inf')
    best_id = None
    
    for generation in results:
        for solution_id, fitness_data in results[generation].items():
            if fitness_data.agg_fitness > best_fitness:
                best_fitness = fitness_data.agg_fitness
                best_id = solution_id
    
    if best_id:
        print(f"\nBest solution ID: {best_id}")
        print(f"Best aggregated fitness: {best_fitness:.4f}")
        
        # You can retrieve the full configuration if needed:
        # best_config = optimizer.get_optimization_result_configuration(best_id)
        # best_config.write("best_solution.json")


if __name__ == "__main__":
    main()

