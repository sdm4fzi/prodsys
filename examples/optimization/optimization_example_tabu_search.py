from prodsys.models.production_system_data import ProductionSystemData
from prodsys.models.scenario_data import ReconfigurationEnum
from prodsys.optimization.adapter_manipulation import add_transformation_operation
from prodsys.optimization.tabu_search import TabuSearchHyperparameters
from prodsys.optimization.optimizer import FileSystemSaveOptimizer
import logging
import os

logger = logging.getLogger(__name__)


def main():
    hyper_parameters = TabuSearchHyperparameters(
        full_save="data/tabu_results",
        seed=22,
        tabu_size=2,
        max_steps=5,
        neighborhood_size=5,
        max_score=5000000,
        number_of_seeds=1,
    )

    def new_transformation(adapter: ProductionSystemData) -> bool:
        print("Transformation function called.")

    add_transformation_operation(
        transformation=ReconfigurationEnum.PRODUCTION_CAPACITY,
        operation=new_transformation,
    )

    base_configuration = ProductionSystemData()
    base_configuration.read_data(
        "examples/optimization/optimization_example/base_scenario.json",
        "examples/optimization/optimization_example/scenario.json",
    )

    initial_solutions = base_configuration
    optimizer = FileSystemSaveOptimizer(
        adapter=base_configuration,
        hyperparameters=hyper_parameters,
        save_folder="data/tabu_results",
        initial_solutions=initial_solutions,
    )

    optimizer.optimize()


if __name__ == "__main__":
    main()
