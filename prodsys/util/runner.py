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
    node_factory,
    linktransportprocess_factory,
)
from prodsys.simulation import logger
from prodsys.util import post_processing, kpi_visualization, util
from prodsys.models import performance_data

VERBOSE = 1

def run_simulation(adapter_object: adapter.ProductionSystemAdapter, run_length: int) -> Runner:
    """
    Runs the simulation for the given adapter and run length.

    Args:
        adapter_object (adapter.ProductionSystemAdapter): Adapter containing the production system to simulate.
        run_length (int): Length of the simulation run.

    Returns:
        Runner: The runner object after simulation.
    """
    runner_object = Runner(adapter=adapter_object)
    runner_object.initialize_simulation()
    runner_object.run(run_length)
    return runner_object


@contextlib.contextmanager
def temp_seed(seed: int):
    """
    Context manager for temporarily setting the seed of the random number generators. Is necessary when optimizing with another random seed but still wanting to use the same seed for the simulation.

    Args:
        seed (int): The seed to set for the simulation run.
    """
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
    """
    Class to represent the simulation runner. It allows to run the simulation based on a provided adapter.

    Args:
        adapter (adapter.ProductionSystemAdapter): The adapter containing the production system to simulate.

    Attributes:
        adapter (adapter.ProductionSystemAdapter): The adapter containing the production system to simulate.
        env (sim.Environment): The environment to run the simulation in.
        time_model_factory (time_model_factory.TimeModelFactory): The time model factory to create the time models.
        state_factory (state_factory.StateFactory): The state factory to create the states.
        process_factory (process_factory.ProcessFactory): The process factory to create the processes.
        queue_factory (queue_factory.QueueFactory): The queue factory to create the queues.
        resource_factory (resource_factory.ResourceFactory): The resource factory to create the resources.
        sink_factory (sink_factory.SinkFactory): The sink factory to create the sinks.
        source_factory (source_factory.SourceFactory): The source factory to create the sources.
        product_factory (product_factory.ProductFactory): The product factory to create the products.
        event_logger (logger.Logger): The event logger to log the events.
        time_stamp (str): The time stamp of the simulation run.
        post_processor (post_processing.PostProcessor): The post processor to process the simulation results.
    """
    adapter: adapter.ProductionSystemAdapter
    env: sim.Environment = Field(
        None, description="The environment to run the simulation in", init=False
    )
    time_model_factory: time_model_factory.TimeModelFactory = Field(
        init=False, default=None
    )
    state_factory: state_factory.StateFactory = Field(init=False, default=None)
    process_factory: process_factory.ProcessFactory = Field(init=False, default=None)
    linktransportprocess_factory: linktransportprocess_factory.LinkTransportProcessFactory = Field(init=False, default=None)
    queue_factory: queue_factory.QueueFactory = Field(init=False, default=None)
    resource_factory: resource_factory.ResourceFactory = Field(init=False, default=None)
    node_factory: node_factory.NodeFactory = Field(init=False, default=None)
    sink_factory: sink_factory.SinkFactory = Field(init=False, default=None)
    source_factory: source_factory.SourceFactory = Field(init=False, default=None)
    product_factory: product_factory.ProductFactory = Field(init=False, default=None)
    event_logger: logger.Logger = Field(init=False, default=None)
    time_stamp: str = Field(init=False, default="")
    post_processor: post_processing.PostProcessor = Field(init=False, default=None)

    class Config:
        arbitrary_types_allowed = True

    def initialize_simulation(self):
        """
        Initializes the simulation by creating the factories and all simulation objects. Needs to be done before running the simulation.
        """
        self.adapter.validate_configuration()
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
                state_factory=self.state_factory,
                queue_factory=self.queue_factory,
                process_factory= self.process_factory
            )
            self.resource_factory.create_resources(self.adapter)

            self.node_factory = node_factory.NodeFactory(
                env=self.env)
            self.node_factory.create_nodes(self.adapter)

            self.product_factory = product_factory.ProductFactory(
                env=self.env,
                process_factory= self.process_factory
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

            self.linktransportprocess_factory = linktransportprocess_factory.LinkTransportProcessFactory(
                time_model_factory=self.time_model_factory,
                source_factory=self.source_factory,
                sink_factory=self.sink_factory,
                resource_factory=self.resource_factory,
                node_factory=self.node_factory,
            )
            self.linktransportprocess_factory.create_processes(self.adapter)

            #TODO: Correct solution to overwrite all!?

            self.resource_factory = resource_factory.ResourceFactory(
                env=self.env,
                state_factory=self.state_factory,
                queue_factory=self.queue_factory,
                process_factory= self.linktransportprocess_factory
            )
            self.resource_factory.create_resources(self.adapter)

            self.product_factory = product_factory.ProductFactory(
                env=self.env,
                process_factory= self.linktransportprocess_factory
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
        """
        Runs the simulation for the given time range.

        Args:
            time_range (int): The time range to run the simulation for.
        """

        t_0 = time.perf_counter()

        self.env.run(time_range)

        t_1 = time.perf_counter()
        self.time_stamp = time.strftime("%Y%m%d-%H%M%S")

    def get_post_processor(self) -> post_processing.PostProcessor:
        """
        Returns the post processor to process the simulation results.

        Returns:
            post_processing.PostProcessor: The post processor to process the simulation results.
        """
        if not self.post_processor:
            self.post_processor = post_processing.PostProcessor(df_raw=self.event_logger.get_data_as_dataframe())
        return self.post_processor


    def print_results(self):
        """
        Prints the aggregated simulation results, comprising the average throughput, WIP, throughput time and the time per state of the resources.
        """
        p = self.get_post_processor()
        kpi_visualization.print_aggregated_data(p)

    def plot_results(self):
        """
        Plots the aggregated simulation results, comprising the throughput time over time, WIP over time, throughput time distribution and the time per state of the resources.
        """
        p = self.get_post_processor()
        kpi_visualization.plot_throughput_time_over_time(p)
        kpi_visualization.plot_WIP(p)
        kpi_visualization.plot_WIP_per_resource(p)
        kpi_visualization.plot_throughput_time_distribution(p)
        kpi_visualization.plot_time_per_state_of_resources(p)

    def get_event_data_of_simulation(self) -> List[performance_data.Event]:
        """
        Returns the event data of the simulation.

        Returns:
            List[performance_data.Event]: The event data of the simulation.
        """
        p = self.get_post_processor()
        df_raw=self.event_logger.get_data_as_dataframe()
        events = []
        df_raw["Expected End Time"].fillna(value=-1, inplace=True)
        df_raw["Target location"].fillna(value="", inplace=True)
        df_raw["Product"].fillna(value="", inplace=True)
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
        """
        Returns the performance data of the simulation.

        Returns:
            performance_data.Performance: The performance data of the simulation.
        """
        p = self.get_post_processor()
        kpis = []
        kpis += p.WIP_KPIs
        kpis += p.throughput_and_output_KPIs
        kpis += p.aggregated_throughput_time_KPIs
        kpis += p.machine_state_KPIS
        event_data = self.get_event_data_of_simulation()
        return performance_data.Performance(kpis=kpis, event_log=event_data)
    
    def get_aggregated_data_simulation_results(self) -> dict:
        """
        Returns the aggregated simulation results.

        Returns:
            dict: The aggregated simulation results.
        """
        p = post_processing.PostProcessor(df_raw=self.event_logger.get_data_as_dataframe())
        return p.get_aggregated_data()

    def save_results_as_csv(self, save_folder="data"):
        """
        Saves the simulation results as .csv-file marked with the time_stamp of simulation and the adapter ID if available.

        Args:
            save_folder (str, optional): The folder to save the results to. Defaults to "data".
        """
        util.prepare_save_folder(save_folder + "/")
        save_name = ""
        if self.adapter.ID:
            save_name = f"{self.adapter.ID}_"
        save_name += self.time_stamp
        self.event_logger.log_data_to_csv(filepath=f"{save_folder}/{save_name}.csv")

    def save_results_as_json(self, save_folder="data"):
        """
        Saves the simulation results as .json-file marked with the time_stamp of simulation and the adapter ID if available.

        Args:
            save_folder (str, optional): The folder to save the results to. Defaults to "data".
        """
        util.prepare_save_folder(save_folder + "/")
        save_name = ""
        if self.adapter.ID:
            save_name = f"{self.adapter.ID}_"
        save_name += self.time_stamp
        self.event_logger.log_data_to_json(filepath=f"{save_folder}/{save_name}.json")

