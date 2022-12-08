from __future__ import annotations

from prodsim import sim
from prodsim import print_util
import time
from prodsim.post_processing import PostProcessor


if __name__ == '__main__':



    sim = sim.Environment()

    # env.load_json('data/simple_example.json')
    sim.load_json('data/base_scenario.json')
    sim.initialize_simulation()

    import time

    t_0 = time.perf_counter()

    sim.run(40000)

    t_1 = time.perf_counter()

    print_util.print_simulation_info(sim, t_0, t_1)    

    sim.data_collector.log_data_to_csv(filepath="data/data23.csv")


    p = PostProcessor(filepath="data/data23.csv")
    p.print_aggregated_data()
    # p.plot_time_per_state_of_resources()
    # p.plot_WIP()
    p.plot_throughput_over_time()
    p.plot_throughput_time_distribution()
    p.plot_time_per_state_of_resources()
    p.plot_WIP_with_range()
    # p.plot_inductive_bpmn()
    # p.save_inductive_petri_net()