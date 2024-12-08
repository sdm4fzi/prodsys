


from prodsys.adapters.json_adapter import JsonProductionSystemAdapter
from prodsys.models.scenario_data import ReconfigurationEnum
from prodsys.optimization.adapter_manipulation import add_transformation_operation
from prodsys.optimization.evolutionary_algorithm import EvolutionaryAlgorithmHyperparameters
from prodsys.optimization.optimizer import Optimizer


def main():
    hyper_parameters = EvolutionaryAlgorithmHyperparameters(
        seed=0, number_of_generations=10, population_size=8, mutation_rate=0.15, crossover_rate=0.1, number_of_seeds=2, number_of_processes=8
    )

    def new_transformation(adapter: JsonProductionSystemAdapter) -> bool:
        print("Mutation function called.")
    add_transformation_operation(transformation=ReconfigurationEnum.PRODUCTION_CAPACITY, operation=new_transformation)



    base_configuration = JsonProductionSystemAdapter()

    base_configuration.read_data(
        "examples/optimization/optimization_example/base_scenario.json",
        "examples/optimization/optimization_example/scenario.json"
    )

    optimizer = Optimizer(
        adapter=base_configuration,
        hyperparameters=hyper_parameters
    )

    optimizer.optimize()

if __name__ == "__main__":
    main()