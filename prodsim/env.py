from __future__ import annotations

from abc import ABC, abstractmethod
from copy import copy
from dataclasses import dataclass, field
from typing import List, Tuple, Union
from functools import partial
from tqdm import tqdm

import contextlib
import numpy as np
import random

import simpy

from . import loader
from . import process
from . import resources
from . import material
from . import sink
from . import source
from . import store
from . import time_model
from . import state
from . import router
from . import request

from . import util
from . import logger

Location = Union[resources.Resource, source.Source, sink.Sink]

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

@dataclass
class Environment(simpy.Environment):
    loader: loader.Loader = field(init=False)
    time_model_factory: time_model.TimeModelFactory = field(init=False)
    state_factory: state.StateFactory = field(init=False)
    process_factory: process.ProcessFactory = field(init=False)
    queue_factory: store.QueueFactory = field(init=False)
    resource_factory: resources.ResourceFactory = field(init=False)
    sink_factory: sink.SinkFactory = field(init=False)
    source_factory: source.SourceFactory = field(init=False)
    material_factory: material.MaterialFactory = field(init=False)
    data_collector: logger.Datacollector = field(init=False)

    pbar: tqdm = field(init=False, default=False)
    last_update: int = field(init=False, default=0)

    def __init__(self) -> None:
        super().__init__()

    def load_json(self, file_path: str) -> None:
        self.loader = loader.JsonLoader()
        self.loader.read_data(file_path=file_path)

    def run(self, time_range:int):
        with temp_seed(self.loader.seed):
            if VERBOSE == 1:
                self.pbar = tqdm(total=time_range)

            super().run(time_range)
            if VERBOSE == 1:
                self.pbar.update(time_range - self.last_update)
                self.pbar.refresh()
    
    def initialize_simulation(self):
        with temp_seed(self.loader.seed):
            self.time_model_factory = time_model.TimeModelFactory(
                configuration_data=self.loader.time_model_data
            )
            self.time_model_factory.create_time_models()

            self.state_factory = state.StateFactory(
                self.loader.state_data, self, self.time_model_factory
            )
            self.state_factory.create_states()

            self.process_factory = process.ProcessFactory(
                self.loader.process_data, self.time_model_factory
            )
            self.process_factory.create_processes()

            self.queue_factory = store.QueueFactory(self.loader.queue_data, self)
            self.queue_factory.create_queues()

            self.resource_factory = resources.ResourceFactory(
                self.loader.resource_data,
                self,
                self.process_factory,
                self.state_factory,
                self.queue_factory,
            )
            self.resource_factory.create_resources()

            self.material_factory = material.MaterialFactory(
                self.loader.material_data, self, self.process_factory
            )

            self.sink_factory = sink.SinkFactory(
                self.loader.sink_data, self, self.material_factory, self.queue_factory
            )
            self.sink_factory.create_sinks()

            self.source_factory = source.SourceFactory(
                self.loader.source_data,
                self,
                self.material_factory,
                self.time_model_factory,
                self.queue_factory,
                self.resource_factory,
                self.sink_factory,
            )
            self.source_factory.create_sources()

            self.resource_factory.start_resources()
            self.source_factory.start_sources()

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

    def get_next_process(self, material: material.Material):
        pass

    def get_next_resource(self, resource: resources.Resource):
        pass

    def request_process_of_resource(self, request: request.Request) -> None:
        if VERBOSE == 1:
            now = round(self.now)
            if now > self.last_update:
                self.pbar.update(now - self.last_update)
                self.last_update = now
        _controller = request.get_resource().get_controller()
        # self.process(_controller.request(request))
        _controller.request(request)
