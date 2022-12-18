from __future__ import annotations

import prodsim

if __name__ == '__main__':

    adapter_object = prodsim.adapter.JsonAdapter()

    # adapter_object.read_data('data/simple_example.json')
    adapter_object.read_data('data/example_configuration.json')
    # adapter_object.write_data("data/example_configuration.json")


    runner_object = prodsim.runner.Runner(adapter=adapter_object)
    runner_object.initialize_simulation()
    runner_object.run(3000)
    # runner_object.save_results_as_csv()
    # runner_object.save_results_as_json()
