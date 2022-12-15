from __future__ import annotations

import contextlib
import random
from pydantic import BaseModel, Field

import numpy as np


from prodsim import adapter, sim, logger
from prodsim.factories import (
    state_factory,
    time_model_factory,
    process_factory,
    queue_factory,
    resource_factory,
    material_factory,
    sink_factory,
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
    # loader: loader.Loader = field(init=False, default=None)
    # time_model_factory: time_model_factory.TimeModelFactory = field(init=False, default=None)
    # state_factory: state_factory.StateFactory = field(init=False, default=None)
    # process_factory: process.ProcessFactory = field(init=False, default=None)
    # queue_factory: store.QueueFactory = field(init=False, default=None)
    # resource_factory: resources.ResourceFactory = field(init=False, default=None)
    # sink_factory: sink.SinkFactory = field(init=False, default=None)
    # source_factory: source.SourceFactory = field(init=False, default=None)
    # material_factory: material.MaterialFactory = field(init=False, default=None)
    # data_collector: logger.Datacollector = field(init=False, default=None)

    def run(self, time_range: int):
        self.env.run(time_range)

    def initialize_simulation(self):
        with temp_seed(self.adapter.seed):

            print("----------------------------------")

            time_model_factory_object = time_model_factory.TimeModelFactory()
            time_model_factory_object.create_time_model_from_adapter(self.adapter)

            for time_model in time_model_factory_object.time_models:
                print(time_model)

            print("----------------------------------")

            self.env = sim.Environment(seed=self.adapter.seed)

            state_factory_object = state_factory.StateFactory(
                env=self.env, time_model_factory=time_model_factory_object
            )
            state_factory_object.create_states_from_adapter(self.adapter)

            for state in state_factory_object.states:
                print(state)

            print("----------------------------------")

            process_factory_object = process_factory.ProcessFactory(
                time_model_factory=time_model_factory_object
            )
            process_factory_object.create_processes_from_adapter(self.adapter)

            for process in process_factory_object.processes:
                print(process)

            print("----------------------------------q")

            queue_factory_object = queue_factory.QueueFactory(env=self.env)
            queue_factory_object.create_queues_from_adapter(self.adapter)

            for queue in queue_factory_object.queues:
                print(queue)

            print("----------------------------------r")

            resource_factory_object = resource_factory.ResourceFactory(
                env=self.env,
                process_factory=process_factory_object,
                state_factory=state_factory_object,
                queue_factory=queue_factory_object,
            )
            resource_factory_object.create_resources_from_adapter(self.adapter)

            for resource in resource_factory_object.resources:
                print(resource.data)

            print("----------------------------------")

            material_factory_object = material_factory.MaterialFactory(
                env=self.env, process_factory=process_factory_object
            )

            sink_factory_object = sink_factory.SinkFactory(
                env=self.env, material_factory=material_factory_object, queue_factory=queue_factory_object
            )

            from . import router

            router_object = router.SimpleRouter(
                resource_factory=resource_factory_object,
                sink_factory=sink_factory_object,
                routing_heuristic=router.ROUTING_HEURISTIC["random"],
            )

            data_collector = logger.Datacollector()
            for r in resource_factory_object.resources:
                all_states = r.states + r.production_states
                for __state in all_states:
                    data_collector.register_patch(
                        __state.state_info,
                        attr=[
                            "log_start_state",
                            "log_start_interrupt_state",
                            "log_end_interrupt_state",
                            "log_end_state",
                        ],
                        post=logger.post_monitor_state_info,
                    )

            material_factory_object.data_collecter = data_collector

            for material_d in self.adapter.material_data:
                material = material_factory_object.create_material(material_d, router_object)
                print(material)	
            # self.resource_factory = resources.ResourceFactory(
            #     self.loader.resource_data,
            #     self,
            #     self.process_factory,
            #     self.state_factory,
            #     self.queue_factory,
            # )
            # self.resource_factory.create_resources()

            # self.material_factory = material.MaterialFactory(
            #     self.loader.material_data, self, self.process_factory
            # )

            # self.sink_factory = sink.SinkFactory(
            #     self.loader.sink_data, self, self.material_factory, self.queue_factory
            # )
            # self.sink_factory.create_sinks()

            # self.source_factory = source.SourceFactory(
            #     self.loader.source_data,
            #     self,
            #     self.material_factory,
            #     self.time_model_factory,
            #     self.queue_factory,
            #     self.resource_factory,
            #     self.sink_factory,
            # )
            # self.source_factory.create_sources()

            # self.resource_factory.start_resources()
            # self.source_factory.start_sources()

            # self.data_collector = logger.Datacollector()
            # for r in self.resource_factory.resources:
            #     all_states = r.states + r.production_states
            #     for __state in all_states:
            #         self.data_collector.register_patch(
            #             __state.state_info,
            #             attr=[
            #                 "log_start_state",
            #                 "log_start_interrupt_state",
            #                 "log_end_interrupt_state",
            #                 "log_end_state",
            #             ],
            #             post=logger.post_monitor_state_info,
            #         )

            # self.material_factory.data_collecter = self.data_collector
