from __future__ import annotations

import prodsim

if __name__ == '__main__':

    adapter_object = prodsim.adapters.JsonAdapter()

    # adapter_object.read_data('data/simple_example.json')
    adapter_object.read_data('data/example_configuration.json')
    # adapter_object.read_data('data/ea_results/f_00_5.json')
    json = adapter_object.json()
    # with open('data/example_configuration_new.json', 'w') as f:
    #     f.write(json)
    # adapter_object.write_data("data/example_configuration.json")


    runner_object = prodsim.runner.Runner(adapter=adapter_object)
    runner_object.initialize_simulation()
    runner_object.run(3000)
    runner_object.print_results()
    runner_object.plot_results()
    runner_object.save_results_as_csv()
    # runner_object.save_results_as_json()
