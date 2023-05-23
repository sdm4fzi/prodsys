from __future__ import annotations

import contextlib
import random
from pydantic import BaseModel, Field
from typing import List

import numpy as np
import time
from functools import cached_property

from prodsys.adapters import adapter
from prodsys.simulation import sim
from prodsys.factories import (
    state_factory,
    time_model_factory,
    process_factory,
    queue_factory,
    resource_factory,
    product_factory,
    sink_factory,
    source_factory,
)
from prodsys.simulation import logger
from prodsys.util import post_processing, kpi_visualization
from prodsys.data_structures import performance_data

VERBOSE = 1

def run_simulation(adapter_object: adapter.ProductionSystemAdapter, run_length: int) -> Runner:
    runner_object = Runner(adapter=adapter_object)
    runner_object.initialize_simulation()
    runner_object.run(run_length)
    return runner_object


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
    adapter: adapter.ProductionSystemAdapter
    env: sim.Environment = Field(
        None, description="The environment to run the simulation in", init=False
    )
    time_model_factory: time_model_factory.TimeModelFactory = Field(
        init=False, default=None
    )
    state_factory: state_factory.StateFactory = Field(init=False, default=None)
    process_factory: process_factory.ProcessFactory = Field(init=False, default=None)
    queue_factory: queue_factory.QueueFactory = Field(init=False, default=None)
    resource_factory: resource_factory.ResourceFactory = Field(init=False, default=None)
    sink_factory: sink_factory.SinkFactory = Field(init=False, default=None)
    source_factory: source_factory.SourceFactory = Field(init=False, default=None)
    product_factory: product_factory.ProductFactory = Field(init=False, default=None)
    event_logger: logger.Logger = Field(init=False, default=None)
    time_stamp: str = Field(init=False, default="")
    post_processor: post_processing.PostProcessor = Field(init=False, default=None)

    class Config:
        arbitrary_types_allowed = True

    def initialize_simulation(self):
        with temp_seed(self.adapter.seed):

            self.time_model_factory = time_model_factory.TimeModelFactory()
            self.time_model_factory.create_time_models(self.adapter)

            self.env = sim.Environment(seed=self.adapter.seed)

            self.state_factory = state_factory.StateFactory(
                env=self.env, time_model_factory=self.time_model_factory
            )
            self.state_factory.create_states(self.adapter)

            self.process_factory = process_factory.ProcessFactory(
                time_model_factory=self.time_model_factory
            )
            self.process_factory.create_processes(self.adapter)

            self.queue_factory = queue_factory.QueueFactory(env=self.env)
            self.queue_factory.create_queues(self.adapter)

            self.resource_factory = resource_factory.ResourceFactory(
                env=self.env,
                process_factory=self.process_factory,
                state_factory=self.state_factory,
                queue_factory=self.queue_factory,
            )
            self.resource_factory.create_resources(self.adapter)

            self.product_factory = product_factory.ProductFactory(
                env=self.env, process_factory=self.process_factory
            )

            self.sink_factory = sink_factory.SinkFactory(
                env=self.env,
                product_factory=self.product_factory,
                queue_factory=self.queue_factory,
            )

            self.sink_factory.create_sinks(self.adapter)

            self.event_logger = logger.EventLogger()
            self.event_logger.observe_resource_states(self.resource_factory)

            self.product_factory.event_logger = self.event_logger

            self.source_factory = source_factory.SourceFactory(
                env=self.env,
                product_factory=self.product_factory,
                time_model_factory=self.time_model_factory,
                queue_factory=self.queue_factory,
                resource_factory=self.resource_factory,
                sink_factory=self.sink_factory,
            )
            self.source_factory.create_sources(self.adapter)

            self.resource_factory.start_resources()
            self.source_factory.start_sources()

    def run(self, time_range: int):

        t_0 = time.perf_counter()

        self.env.run(time_range)

        t_1 = time.perf_counter()
        self.time_stamp = time.strftime("%Y%m%d-%H%M%S")

    def get_post_processor(self) -> post_processing.PostProcessor:
        if not self.post_processor:
            self.post_processor = post_processing.PostProcessor(df_raw=self.event_logger.get_data_as_dataframe())
        return self.post_processor


    def print_results(self):
        p = self.get_post_processor()
        kpi_visualization.print_aggregated_data(p)

    def plot_results(self):
        p = self.get_post_processor()
        kpi_visualization.plot_throughput_time_over_time(p)
        kpi_visualization.plot_WIP(p)
        kpi_visualization.plot_WIP_with_range(p)
        kpi_visualization.plot_throughput_time_distribution(p)
        kpi_visualization.plot_time_per_state_of_resources(p)

    def get_event_data_of_simulation(self) -> List[performance_data.Event]:
        p = self.get_post_processor()
        df_raw=self.event_logger.get_data_as_dataframe()
        events = []
        for index, row in df_raw.iterrows():
            events.append(
                performance_data.Event(
                    time=row["Time"],
                    resource=row["Resource"],
                    state=row["State"],
                    state_type=row["State Type"],
                    activity=row["Activity"],
                    product=row["Product"],
                    expected_end_time=row["Expected End Time"],
                    target_location=row["Target location"],
                )
            )
        return events
    
    def get_performance_data(self) -> performance_data.Performance:
        p = self.get_post_processor()
        kpis = []
        kpis += p.WIP_KPIs
        kpis += p.throughput_and_output_KPIs
        kpis += p.aggregated_throughput_time_KPIs
        kpis += p.machine_state_KPIS
        event_data = self.get_event_data_of_simulation()
        return performance_data.Performance(kpis=kpis, event_log=event_data)
    
    def get_aggregated_data_simulation_results(self) -> dict:
        p = post_processing.PostProcessor(df_raw=self.event_logger.get_data_as_dataframe())
        return p.get_aggregated_data()

    def save_results_as_csv(self, save_folder="data"):
        self.event_logger.log_data_to_csv(filepath=f"{save_folder}/{self.time_stamp}.csv")

    def save_results_as_json(self, save_folder="data"):
        self.event_logger.log_data_to_json(filepath=f"{save_folder}/{self.time_stamp}.json")

