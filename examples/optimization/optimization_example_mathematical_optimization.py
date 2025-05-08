from prodsys.models.production_system_data import ProductionSystemData
from prodsys.models.scenario_data import ReconfigurationEnum
from prodsys.optimization.adapter_manipulation import add_transformation_operation
from prodsys.optimization.math_opt import MathOptHyperparameters
from prodsys.optimization.optimizer import FileSystemSaveOptimizer, Optimizer
import time
import logging

logger = logging.getLogger(__name__)


def main():
    # Setzen der Hyperparameter für mathematische Optimierung
    hyper_parameters = MathOptHyperparameters(
        full_save="data/math_results",
        optimization_time_portion=1,
        number_of_solutions=1,
        adjusted_number_of_transport_resources=2,
        number_of_seeds=2,
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

    optimizer = FileSystemSaveOptimizer(
        adapter=base_configuration,
        hyperparameters=hyper_parameters,
        save_folder="data/math_results",
    )

    optimizer.optimize()


if __name__ == "__main__":
    main()
