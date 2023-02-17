from __future__ import annotations

import prodsim
from prodsim.simulation import resources

if __name__ == '__main__':

    adapter_object = prodsim.adapters.JsonAdapter()

    adapter_object.read_data('data/example_configuration.json')
    # adapter_object.write_data("data/example_configuration.json")


    runner_object = prodsim.runner.Runner(adapter=adapter_object)
    runner_object.initialize_simulation()
    runner_object.run(50000)
    runner_object.print_results()
    # runner_object.plot_results()
    runner_object.save_results_as_csv()
    # runner_object.save_results_as_json()

    performance = runner_object.get_performance_data()
    for kpi in performance.kpis:
        print(kpi)
    
    for event in performance.event_log[0:10]:
        print(event)