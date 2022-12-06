from __future__ import annotations

from prodsim import adapter


if __name__ == '__main__':

    adapter = adapter.JsonAdapter()

    adapter.read_data('data/simple_example.json')
    for time_model_data in adapter.time_model_data:
        print(time_model_data)

    from prodsim.time_model import TimeModelFactory

    time_model_factory = TimeModelFactory()
    time_model_factory.create_time_model_from_adapter(adapter)
        

    # # env.load_json('data/simple_example.json')
    # env.load_json('data/base_scenario.json')
    # env.initialize_simulation()

    # import time

    # t_0 = time.perf_counter()

    # env.run(40000)

    # t_1 = time.perf_counter()

    # print_util.print_simulation_info(env, t_0, t_1)

    # env.data_collector.log_data_to_csv(filepath="data/data23.csv")


    # p = PostProcessor(filepath="data/data23.csv")
    # p.print_aggregated_data()
    # # p.plot_time_per_state_of_resources()
    # # p.plot_WIP()
    # p.plot_throughput_over_time()
    # p.plot_throughput_time_distribution()
    # p.plot_time_per_state_of_resources()
    # p.plot_WIP_with_range()
    # # p.plot_inductive_bpmn()
    # # p.save_inductive_petri_net()

