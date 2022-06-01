from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

import simpy
import env
import base
import process
# from process import Process, ProcessFactory
import state
import copy
import material
import control
from time_model import TimeModelFactory, TimeModel
import router


@dataclass
class Queue(simpy.FilterStore, base.IDEntity):
    env: env.Environment
    capacity: int = field(default=1)

    def __post_init__(self):
        super(Queue, self).__init__(self.env)


@dataclass
class QueueFactory:
    data: dict
    env: env.Environment
    queues: List[Queue] = field(default_factory=list, init=False)

    def create_queues(self):
        queues = self.data['queues']
        for values in queues.values():
            self.add_queue(values)

    def add_queue(self, values: dict):
        queue = Queue(ID=values['ID'],
                      description=values['description'],
                      env=self.env,
                      capacity=values['capacity']
                      )
        self.queues.append(queue)

    def get_queue(self, ID) -> Queue:
        return [q for q in self.queues if q.ID == ID].pop()

    def get_queues(self, IDs: List[str]) -> List[Queue]:
        return [q for q in self.queues if q.ID in IDs]


@dataclass
class Source(base.IDEntity):
    env: env.Environment
    material_factory: material.MaterialFactory
    material_type: str
    time_model: TimeModel
    router: router.SimpleRouter

    def start_source(self):
        self.env.process(self.create_material())

    def create_material(self):
        print("create material")
        while True:
            yield self.env.timeout(self.time_model.get_next_time())
            __material = self.material_factory.create_material(type=self.material_type, router=self.router)
            __material.process = self.env.process(__material.process_material())


@dataclass
class SourceFactory:
    data: dict
    env: env.Environment
    material_factory: material.MaterialFactory
    time_model_factory: TimeModelFactory
    routers: dict

    sources: List[Source] = field(default_factory=list, init=False)

    def create_sources(self):
        sources = self.data['sources']
        for values in sources.values():
            self.add_source(values)

    def get_router(self, router: str):
        return self.routers[router]

    def add_source(self, values: dict):
        router = self.get_router(values['router'])
        time_model = self.time_model_factory.get_time_model(values['time_model_id'])
        source = Source(ID=values['ID'], description=values['description'],
                        env=self.env, material_factory=self.material_factory,
                        material_type=values['material_type'],
                        time_model=time_model,
                        router=router
                        )
        self.sources.append(source)

    def start_sources(self):
        for _source in self.sources:
            _source.start_source()

    def get_source(self, ID) -> Source:
        return [s for s in self.sources if s.ID == ID].pop()

    def get_sources(self, IDs: List[str]) -> List[Source]:
        return [s for s in self.sources if s.ID in IDs]

    def get_sources_with_material_type(self, __material_type: str):
        return [s for s in self.sources if __material_type == s.material_type]



@dataclass
class Resource(ABC, simpy.Resource, base.IDEntity):
    env: env.Environment
    processes: List[process.Process]
    capacity: int = field(default=1)
    input_queues: List[Queue] = field(default_factory=list, init=False)
    output_queues: List[Queue] = field(default_factory=list, init=False)
    parts_made: int = field(default=0, init=False)
    available: simpy.Event = field(default=None, init=False)
    active: simpy.Event = field(default=None, init=False)
    states: List[state.State] = field(default_factory=list, init=False)
    production_states: List[state.State] = field(default_factory=list, init=False)
    setup_states: List[state.State] = field(default_factory=list, init=False)
    controller: control.Controller = field(default=None, init=False)

    def __post_init__(self):
        super(Resource, self).__init__(self.env)
        self.available = simpy.Event(self.env)
        self.active = simpy.Event(self.env).succeed()

    @abstractmethod
    def change_state(self, input_state: state.State) -> None:
        pass

    def add_input_queues(self, input_queues: List[Queue]):
        self.input_queues.extend(input_queues)

    def add_output_queues(self, output_queues: List[Queue]):
        self.output_queues.extend(output_queues)

    def add_state(self, input_state: state.State) -> None:
        self.states.append(input_state)
        input_state.resource = self

    def add_production_state(self, input_state: state.State) -> None:
        self.production_states.append(input_state)
        input_state.resource = self

    def start_states(self):
        for actual_state in self.states:
            actual_state.activate_state()
            actual_state.process = self.env.process(actual_state.process_state())

    @abstractmethod
    def process_states(self) -> None:
        pass

    @abstractmethod
    def reactivate(self):
        pass

    @abstractmethod
    def interrupt_state(self):
        pass

    def interrupt_states(self):
        for state in self.production_states:
            if state.process:
                self.env.process(state.interrupt_process())

    def run_process(self, process: process.Process):
        for input_state in self.production_states:
            if input_state.description == process.description:
                input_state.process = self.env.process(input_state.process_state())
                return input_state.process

    def get_process(self, process: process.Process):
        for actual_state in self.production_states:
            if actual_state.description == process.description:
                return actual_state

    def request_process(self, process: process.Process):
        self.env.process(self.controller.request(process, self))

    def get_states(self) -> List[state.State]:
        return self.states

    def activate(self):
        self.active.succeed()
        for actual_state in self.states:
            actual_state.activate()

    def request_repair(self):
        pass

    def setup(self, _process: process.Process):
        for input_state in self.setup_states:
            if input_state.description == _process.description:
                input_state.process = self.env.process(input_state.process_state())
                return input_state.process


class ConcreteResource(Resource):

    def __post_init__(self):
        super(Resource, self).__init__(self.env)
        self.active = simpy.Event(self.env).succeed()
        self.req = simpy.Event(self.env)
        self.available = simpy.Event(self.env)

    def change_state(self, input_state: state.State) -> None:
        pass

    def add_state(self, input_state: state.State) -> None:
        self.states.append(input_state)
        input_state.resource = self

    def process_states(self) -> None:
        for state in self.states:
            process = self.env.process(state.process_state())
            state.process = process

    def reactivate(self):
        for _state in self.states:
            _state.activate()

    def interrupt_state(self):
        for actual_state in self.states:
            if type(actual_state) == state.ProductionState:
                self.env.process(actual_state.interrupt_process())
                # actual_state.interrupt_process()

    def get_active_states(self) -> List[state.State]:
        pass

    def request_repair(self):
        pass


def register_states(resource: Resource, states: List[state.State], env: env.Environment):
    for actual_state in states:
        copy_state = copy.deepcopy(actual_state)
        copy_state.env = env
        resource.add_state(copy_state)


def register_production_states(resource: Resource, states: List[state.State], env: env.Environment):
    for actual_state in states:
        copy_state = copy.deepcopy(actual_state)
        copy_state.env = env
        resource.add_production_state(copy_state)


def register_production_states_for_processes(resource: Resource, state_factory: state.StateFactory,
                                             _env: env.Environment):
    states: List[state.State] = []
    for process in resource.processes:
        values = {'ID': process.ID, 'description': process.description, 'time_model_id': process.time_model.ID}
        state_factory.add_states(cls=state.ProductionState, values=values)
        _state = state_factory.get_states(IDs=[values['ID']]).pop()
        states.append(_state)
    register_production_states(resource, states, _env)


@dataclass
class ResourceFactory:
    data: dict
    env: env.Environment
    process_factory: process.ProcessFactory
    state_factory: state.StateFactory
    queue_factory: QueueFactory

    resources: List[Resource] = field(default_factory=list, init=False)

    def create_resources(self):
        resources = self.data['resources']
        for values in resources.values():
            self.add_resource(values)

    def add_resource(self, values: dict):
        states = self.state_factory.get_states(values['states'])
        processes = self.process_factory.get_processes(values['processes'])

        resource = ConcreteResource(ID=values['ID'],
                                    description=values['description'],
                                    env=self.env,
                                    capacity=2,
                                    processes=processes,
                                    )
        input_queues = self.queue_factory.get_queues(values['input_queues'])
        output_queues = self.queue_factory.get_queues(values['output_queues'])

        resource.add_input_queues(input_queues)
        resource.add_output_queues(output_queues)

        register_states(resource, states, self.env)
        register_production_states_for_processes(resource, self.state_factory, self.env)
        resource.controller = control.SimpleController(control.FIFO_control_policy)

        self.resources.append(resource)

    def start_resources(self):
        for _resource in self.resources:
            _resource.start_states()

    def get_resource(self, ID):
        return [st for st in self.resources if st.ID == ID].pop()

    def get_resources(self, IDs: List[str]) -> List[Resource]:
        return [r for r in self.resources if r.ID in IDs]

    def get_resources_with_process(self, __process: process.Process):
        return [r for r in self.resources if __process in r.processes]
