import prodsys


if __name__ == "__main__":
    adapter_object = prodsys.adapters.JsonProductionSystemAdapter()

    adapter_object.read_data(
        "examples/modelling_and_simulation/simulation_example_data/example_with_schedule.json"
    )
    # prodsys.set_logging("DEBUG")
    adapter_object.conwip_number = 30
    runner_object = prodsys.runner.Runner(adapter=adapter_object)
    # runner_object.initialize_simulation(use_schedule=False)
    runner_object.initialize_simulation(use_schedule=True, handle_breakdowns=True)
    runner_object.run(8640)
    runner_object.save_results_as_csv()
    runner_object.print_results()
    runner_object.plot_results()
    # runner_object.plot_results_executive()
    # runner_object.save_results_as_json()
