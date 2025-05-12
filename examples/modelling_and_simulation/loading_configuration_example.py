import prodsys


if __name__ == "__main__":
    adapter_object = prodsys.adapters.JsonProductionSystemAdapter()

    adapter_object.read_data(
        "examples/modelling_and_simulation/simulation_example_data/example_configuration.json"
    )
    # prodsys.set_logging("DEBUG")

    runner_object = prodsys.runner.Runner(adapter=adapter_object)
    runner_object.initialize_simulation()
    runner_object.run(2000)
    runner_object.print_results()
    runner_object.plot_results()
    # runner_object.plot_results_executive()
    perf = runner_object.get_performance_data(dynamic_data=True, event_log=False)
    # with open("performance.json", "w") as f:
    #     f.write(perf.model_dump_json(indent=4))
    # runner_object.save_results_as_csv()
    # runner_object.save_results_as_json()
