from __future__ import annotations

import random

from material import MaterialFactory, MaterialInfo
from time_model import TimeModelFactory
from state import StateFactory
from env import Environment
from process import ProcessFactory
from resources import ResourceFactory
from store import QueueFactory
from source import SourceFactory
from sink import SinkFactory
from router import SimpleRouter, FIFO_router, random_router
from logger import Datacollector, pre_monitor_state, post_monitor_state
import logger
import print_util


import json

import numpy as np


if __name__ == '__main__':

    np.random.seed(22)
    random.seed(22)

    env = Environment()

    with open('data/simple_example.json', 'r', encoding='utf-8') as json_file:
        data = json.load(json_file)
    print("data loaded")

    tm_fac = TimeModelFactory(data)

    tm_fac.create_time_models()

    print("time_models created")

    st_fac = StateFactory(data, env, tm_fac)
    st_fac.create_states()

    print("states created")

    pr_fac = ProcessFactory(data, tm_fac)
    pr_fac.create_processes()

    print("processes created")


    q_fac = QueueFactory(data, env)
    q_fac.create_queues()

    print("queues created")

    r_fac = ResourceFactory(data, env, pr_fac, st_fac, q_fac)
    r_fac.create_resources()

    print("resources created")

    m_fac = MaterialFactory(data, env, pr_fac)

    sk_fac = SinkFactory(data, env, m_fac, q_fac)
    sk_fac.create_sinks()

    print("sinks created")

    router = SimpleRouter(env=env, resource_process_registry=r_fac, routing_heuristic=random_router, sink_registry=sk_fac)
    # router = SimpleRouter(env=env, resource_process_registry=r_fac, routing_heuristic=FIFO_router)
    router_dict = {'SimpleRouter': router}

    s_fac = SourceFactory(data, env, m_fac, tm_fac, q_fac, router_dict)
    s_fac.create_sources()

    print("sources created")

    r_fac.start_resources()
    s_fac.start_sources()

    dc = Datacollector()
    for r in r_fac.resources:
        all_states = r.states + r.production_states
        for __state in all_states:
             dc.register_patch(__state.state_info, attr=['log_start_state', 'log_start_interrupt_state', 'log_end_interrupt_state', 'log_end_state'], 
                               post=logger.post_monitor_state_info)

    m_fac.data_collecter = dc       

    import time

    t_0 = time.perf_counter()

    env.run(40000)

    t_1 = time.perf_counter()

    print_util.print_simulation_info(env, m_fac, r_fac, q_fac, t_0, t_1)    

    dc.log_data_to_csv(filepath="data/data22.csv")

    from post_processing import PostProcessor

    p = PostProcessor(filepath="data/data22.csv")
    p.plot_time_per_state_of_resources()
    p.plot_WIP()
    p.plot_throughput_over_time()
    p.plot_throughput_time_distribution()
    p.plot_inductive_bpmn()
    p.save_inductive_petri_net()