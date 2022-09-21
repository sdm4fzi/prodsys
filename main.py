from __future__ import annotations

import env
import print_util
import time
from post_processing import PostProcessor


if __name__ == '__main__':



    env = env.Environment()

    env.load_json('data/simple_example.json')
    env.initialize_simulation()

    import time

    t_0 = time.perf_counter()

    env.run(40000)

    t_1 = time.perf_counter()

    print_util.print_simulation_info(env, t_0, t_1)    

    env.data_collector.log_data_to_csv(filepath="data/data21.csv")


    p = PostProcessor(filepath="data/data21.csv")
    p.print_aggregated_data()
    # p.plot_time_per_state_of_resources()
    # p.plot_WIP()
    # p.plot_throughput_over_time()
    # p.plot_throughput_time_distribution()
    # p.plot_inductive_bpmn()
    # p.save_inductive_petri_net()