from prodsys.adapters.json_adapter import JsonProductionSystemAdapter
from prodsys.models.scenario_data import ReconfigurationEnum
from prodsys.optimization.adapter_manipulation import add_transformation_operation
from prodsys.optimization.simulated_annealing import SimulatedAnnealingHyperparameters
from prodsys.optimization.optimizer import Optimizer
import time
import logging

logger = logging.getLogger(__name__)

def main():
    # Setzen der Hyperparameter entsprechend dem alten Beispiel
    hyper_parameters = SimulatedAnnealingHyperparameters(
        seed=22,  # Verwendung des festgelegten Seeds aus dem alten Code
        Tmax=10000,
        Tmin=1,
        steps=4,
        updates=300,
        number_of_seeds=2
    )

    def new_transformation(adapter: JsonProductionSystemAdapter) -> bool:
        print("Transformation function called.")
    add_transformation_operation(transformation=ReconfigurationEnum.PRODUCTION_CAPACITY, operation=new_transformation)

    base_configuration = JsonProductionSystemAdapter()
    base_configuration.read_data(
        "examples/optimization/optimization_example/base_scenario.json",
        "examples/optimization/optimization_example/scenario.json"
    )

    optimizer = Optimizer(
        adapter=base_configuration,
        hyperparameters=hyper_parameters,
        save_folder="data/anneal_results"
    )

    # Ausführung der vollständigen Optimierung
    optimizer.optimize()


if __name__ == "__main__":
    main()
