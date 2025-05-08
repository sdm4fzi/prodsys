import json
import prodsys
from prodsys.models.production_system_data import add_default_queues_to_adapter


if __name__ == "__main__":
    adapter_object = prodsys.ProductionSystemData.read(
        "examples/modelling_and_simulation/simulation_example_data/example_configuration.json"
    )
    prodsys.set_logging("DEBUG")
    adapter_object = add_default_queues_to_adapter(adapter_object)
    runner_object = prodsys.runner.Runner(adapter=adapter_object)
    runner_object.initialize_simulation()
    runner_object.run(200000)
    runner_object.print_results()
    # runner_object.plot_results()
    # runner_object.plot_results_executive()
    # runner_object.save_results_as_csv()
    # runner_object.save_results_as_json()
