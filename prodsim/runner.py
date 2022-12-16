from __future__ import annotations

import contextlib
import random
from pydantic import BaseModel, Field

import numpy as np
import time

from prodsim import adapter, sim, logger, router
from prodsim.factories import (
    state_factory,
    time_model_factory,
    process_factory,
    queue_factory,
    resource_factory,
    material_factory,
    sink_factory,
    source_factory,
)

VERBOSE = 1


@contextlib.contextmanager
def temp_seed(seed):
    np_state = np.random.get_state()
    p_state = random.getstate()
    np.random.seed(seed)
    random.seed(seed)
    try:
        yield
    finally:
        np.random.set_state(np_state)
        random.setstate(p_state)


class Runner(BaseModel):
    adapter: adapter.Adapter
    env: sim.Environment = Field(
        None, description="The environment to run the simulation in", init=False
    )
    time_model_factory: time_model_factory.TimeModelFactory = Field(init=False, default=None)
    state_factory: state_factory.StateFactory = Field(init=False, default=None)
    process_factory: process_factory.ProcessFactory = Field(init=False, default=None)
    queue_factory: queue_factory.QueueFactory = Field(init=False, default=None)
    resource_factory: resource_factory.ResourceFactory = Field(init=False, default=None)
    sink_factory: sink_factory.SinkFactory = Field(init=False, default=None)
    source_factory: source_factory.SourceFactory = Field(init=False, default=None)
    material_factory: material_factory.MaterialFactory = Field(init=False, default=None)
    data_collector: logger.Datacollector = Field(init=False, default=None)
    
    def initialize_simulation(self):
        with temp_seed(self.adapter.seed):

            self.time_model_factory = time_model_factory.TimeModelFactory()
            self.time_model_factory.create_time_model_from_adapter(self.adapter)

            self.env = sim.Environment(seed=self.adapter.seed)

            self.state_factory = state_factory.StateFactory(
                env=self.env, time_model_factory=self.time_model_factory
            )
            self.state_factory.create_states_from_adapter(self.adapter)

            self.process_factory = process_factory.ProcessFactory(
                time_model_factory=self.time_model_factory
            )
            self.process_factory.create_processes_from_adapter(self.adapter)

            self.queue_factory = queue_factory.QueueFactory(env=self.env)
            self.queue_factory.create_queues_from_adapter(self.adapter)

            self.resource_factory = resource_factory.ResourceFactory(
                env=self.env,
                process_factory=self.process_factory,
                state_factory=self.state_factory,
                queue_factory=self.queue_factory,
            )
            self.resource_factory.create_resources_from_adapter(self.adapter)

            self.material_factory = material_factory.MaterialFactory(
                env=self.env, process_factory=self.process_factory
            )

            self.sink_factory = sink_factory.SinkFactory(
                env=self.env,
                material_factory=self.material_factory,
                queue_factory=self.queue_factory,
            )

            self.data_collector = logger.Datacollector()
            for r in self.resource_factory.resources:
                all_states = r.states + r.production_states
                for __state in all_states:
                    self.data_collector.register_patch(
                        __state.state_info,
                        attr=[
                            "log_start_state",
                            "log_start_interrupt_state",
                            "log_end_interrupt_state",
                            "log_end_state",
                        ],
                        post=logger.post_monitor_state_info,
                    )

            self.material_factory.data_collecter = self.data_collector

            source_factory_object = source_factory.SourceFactory(
                env=self.env,
                material_factory=self.material_factory,
                time_model_factory=self.time_model_factory,
                queue_factory=self.queue_factory,
                resource_factory=self.resource_factory,
                sink_factory=self.sink_factory,
            )
            source_factory_object.create_sources_from_adapter(self.adapter)

            self.resource_factory.start_resources()
            source_factory_object.start_sources()

    def run(self, time_range: int):

        t_0 = time.perf_counter()

        self.env.run(time_range)

        t_1 = time.perf_counter()
        time_stamp = time.strftime("%Y%m%d-%H%M%S")	

        # print_util.print_simulation_info(env, t_0, t_1)

        self.data_collector.log_data_to_csv(filepath=f"data/{time_stamp}.csv")

        # p = PostProcessor(filepath="data/data23.csv")
        # p.print_aggregated_data()
        # # p.plot_time_per_state_of_resources()
        # # p.plot_WIP()
        # p.plot_throughput_over_time()
        # p.plot_throughput_time_distribution()
        # p.plot_time_per_state_of_resources()
        # p.plot_WIP_with_range()
        # p.plot_inductive_bpmn()
        # p.save_inductive_petri_net()
