import prodsys


if __name__ == "__main__":
    adapter_object = prodsys.adapters.JsonProductionSystemAdapter()

    adapter_object.read_data(
        "examples/modelling_and_simulation/simulation_example_data/example_configuration.json"
    )
    # prodsys.set_logging("DEBUG")

    runner_object = prodsys.runner.Runner(adapter=adapter_object)
    runner_object.initialize_simulation()
    runner_object.run(20000)
    runner_object.print_results()
    runner_object.plot_results()
    runner_object.plot_results_executive()
    # runner_object.save_results_as_csv()
    # runner_object.save_results_as_json()
