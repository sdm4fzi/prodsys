from __future__ import annotations

import random

from material import MaterialFactory
from time_model import TimeModelFactory
from state import StateFactory
from env import Environment
from process import ProcessFactory
from resource import ResourceFactory, QueueFactory, SourceFactory
from router import SimpleRouter, FIFO_router, random_router

import json

import numpy as np

if __name__ == '__main__':

    np.random.seed(20)
    random.seed(20)

    env = Environment()

    with open('simple_example.json', 'r', encoding='utf-8') as json_file:
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

    router = SimpleRouter(env=env, resource_process_registry=r_fac, routing_heuristic=random_router)
    # router = SimpleRouter(env=env, resource_process_registry=r_fac, routing_heuristic=FIFO_router)
    router_dict = {'SimpleRouter': router}

    s_fac = SourceFactory(data, env, m_fac, tm_fac, router_dict)
    s_fac.create_sources()

    print("sources created")

    r_fac.start_resources()
    s_fac.start_sources()

    from logger_2 import Datacollector, post_monitor_resource

    r1 = r_fac.get_resource(ID='R1')

    dc = Datacollector()
    # dc.register_patch(r1, attr=['put', 'get', 'request', 'release'],
    for r in r_fac.resources:
        dc.register_patch(r, attr=['release', 'request'],
                              post=post_monitor_resource)

    import time

    t_0 = time.perf_counter()

    # env.run(10000)
    env.run(500000)
    for resource in r_fac.resources:
        print("_________________")
        print(resource.description, resource.parts_made, "items: ", len(resource.input_queues[0].items),
        len(resource.output_queues[0].items), len(resource.users))
        for m in resource.input_queues[0].items:
            print("\t", m.ID, m.description)
        print("\t", "_________________")
        for m in resource.output_queues[0].items:
            print("\t", m.ID, m.description)

    a = 0
    for m in m_fac.materials:
        if m.finished:
            a += 1
    print(a)
    print("created material", len(m_fac.materials), "finished material", a, "wip", len(m_fac.materials) - a)

    print("simulated: ", env.now / 60 / 24, "days in:", time.perf_counter() - t_0, "seconds")

    # TODO: create graph with resources, process and material

    import pandas as pd

    df = pd.DataFrame(dc.data['Resources'])

    print(len(df))

    # TODO: create Transformer class in environment


    # print(dc.data)