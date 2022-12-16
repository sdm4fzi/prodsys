from __future__ import annotations

import prodsim
# from prodsim import loader


if __name__ == '__main__':

    adapter_object = prodsim.adapter.JsonAdapter()

    adapter_object.read_data('data/simple_example.json')
    for time_model_data in adapter_object.time_model_data:
        print(time_model_data)

    print("----------------------------------")

    for state_data in adapter_object.state_data:
        print(state_data)

    print("----------------------------------")


    for process_data in adapter_object.process_data:
        print(process_data)

    print("----------------------------------")

    for queue_data in adapter_object.queue_data:
        print(queue_data)

    
    print("----------------------------------")

    for resource_data in adapter_object.resource_data:
        print(type(resource_data))
        print(resource_data)

    print("----------------------------------")

    for material_data in adapter_object.material_data:
        print(material_data)

    print("----------------------------------")


    runner_object = prodsim.runner.Runner(adapter=adapter_object)
    runner_object.initialize_simulation()





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
