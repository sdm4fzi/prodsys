from prodsys.adapters.json_adapter import JsonProductionSystemAdapter
from prodsys.models.scenario_data import ReconfigurationEnum
from prodsys.optimization.adapter_manipulation import add_transformation_operation
from prodsys.optimization.tabu_search import TabuSearchHyperparameters
from prodsys.optimization.optimizer import Optimizer
import logging

logger = logging.getLogger(__name__)

def main():
    # Setzen der Hyperparameter für den Tabu-Suchalgorithmus
    hyper_parameters = TabuSearchHyperparameters(
        seed=22,  # Verwendung des festgelegten Seeds aus dem alten Code
        tabu_size=10,
        max_steps=300,
        max_score=500,
        number_of_seeds=2
    )
    # FIXME: this is not working!

    def new_transformation(adapter: JsonProductionSystemAdapter) -> bool:
        print("Transformation function called.")
    add_transformation_operation(transformation=ReconfigurationEnum.PRODUCTION_CAPACITY, operation=new_transformation)

    base_configuration = JsonProductionSystemAdapter()
    base_configuration.read_data(
        "examples/optimization/optimization_example/base_scenario.json",
        "examples/optimization/optimization_example/scenario.json"
    )
    #if base_configuration.scenario_data != None:
    #    logger.error("No scenario data loaded.")
    #    return
    optimizer = Optimizer(
        adapter=base_configuration,
        hyperparameters=hyper_parameters,
        save_folder="data/tabu_results", 
    )

    # Ausführung der vollständigen Optimierung
    optimizer.optimize()

if __name__ == "__main__":
    main()