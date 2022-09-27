from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict

import simpy
import env
import base
import process
import state
import copy
import store
import control
from util import get_class_from_str


@dataclass
class Resource(ABC, simpy.Resource, base.IDEntity):
    env: env.Environment
    processes: List[process.Process]
    location: List[int]
    capacity: int = field(default=1)
    input_queues: List[store.Queue] = field(default_factory=list, init=False)
    output_queues: List[store.Queue] = field(default_factory=list, init=False)
    parts_made: int = field(default=0, init=False)
    available: simpy.Event = field(default=None, init=False)
    active: simpy.Event = field(default=None, init=False)
    states: List[state.State] = field(default_factory=list, init=False)
    production_states: List[state.State] = field(default_factory=list, init=False)
    current_process: state.ProductionState = field(default=None, init=False)
    setup_states: List[state.State] = field(default_factory=list, init=False)
    controller: control.Controller = field(default=None, init=False)

    def __post_init__(self):
        super(Resource, self).__init__(self.env)
        self.available = simpy.Event(self.env)
        self.active = simpy.Event(self.env).succeed()

    @abstractmethod
    def change_state(self, input_state: state.State) -> None:
        pass

    def get_controller(self) -> control.Controller:
        return self.controller

    def set_controller(self, controller: control.Controller) -> None:
        self.controller = controller

    def add_input_queues(self, input_queues: List[store.Queue]):
        self.input_queues.extend(input_queues)

    def add_output_queues(self, output_queues: List[store.Queue]):
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
    def reactivate(self):
        pass

    @abstractmethod
    def interrupt_states(self):
        pass

    def get_process(self, process: process.Process) -> state.State:
        for actual_state in self.production_states:
            if actual_state.description == process.description:
                return actual_state

    def get_free_process(self, process: process.Process) -> state.State:
        for actual_state in self.production_states:
            if actual_state.description == process.description and actual_state.process is None:
                return actual_state
        return None

    def get_location(self) -> List[int]:
        return self.location

    def set_location(self, new_location: List[int]) -> None:
        self.location = new_location

    def get_states(self) -> List[state.State]:
        return self.states

    def activate(self):
        self.active.succeed()
        for actual_state in self.production_states:
            if (type(actual_state) == state.ProductionState or type(actual_state) == state.TransportState) and actual_state.process is not None:
                actual_state.activate()

    def request_repair(self):
        pass

    def setup(self, _process: process.Process):
        for input_state in self.setup_states:
            if input_state.description == _process.description:
                self.current_process = input_state
                input_state.process = self.env.process(input_state.process_state())
                return input_state.process


class ConcreteResource(Resource):

    def __post_init__(self):
        super(Resource, self).__init__(self.env)
        self.active = simpy.Event(self.env).succeed()
        self.available = simpy.Event(self.env)

    def change_state(self, input_state: state.State) -> None:
        pass

    def add_state(self, input_state: state.State) -> None:
        self.states.append(input_state)
        input_state.resource = self

    def reactivate(self):
        for _state in self.states:
            _state.activate()

    def interrupt_states(self):
        events = []
        for state in self.production_states:
            if state.process:
                events.append(self.env.process(state.interrupt_process()))
        yield simpy.AllOf(self.env, events)
        

    def get_active_states(self) -> List[state.State]:
        pass

    def request_repair(self):
        pass


def register_states(resource: Resource, states: List[state.State], _env: env.Environment):
    for actual_state in states:
        copy_state = copy.deepcopy(actual_state)
        copy_state.env = _env
        resource.add_state(copy_state)


def register_production_states(resource: Resource, states: List[state.State], _env: env.Environment):
    for actual_state in states:
        copy_state = copy.deepcopy(actual_state)
        copy_state.env = _env
        resource.add_production_state(copy_state)


def register_production_states_for_processes(resource: Resource, state_factory: state.StateFactory,
                                             _env: env.Environment):
    states: List[state.State] = []
    for _process in resource.processes:
        values = {'ID': _process.ID, 'description': _process.description, 'time_model_id': _process.time_model.ID}
        if isinstance(_process, process.ProductionProcess):
            state_factory.add_states(cls=state.ProductionState, values=values)
        if isinstance(_process, process.TransportProcess):
            state_factory.add_states(cls=state.TransportState, values=values)
        _state = state_factory.get_states(IDs=[values['ID']]).pop()
        states.append(_state)
    register_production_states(resource, states, _env)


CONTROLLER_DICT: Dict = {
    'SimpleController': control.SimpleController,
    'TransportController': control.TransportController,
}

CONTROL_POLICY_DICT: Dict = {
    'FIFO': control.FIFO_control_policy,
    'LIFO': control.LIFO_control_policy,
    'SPT': control.SPT_control_policy,
    'SPT_transport': control.SPT_transport_control_policy,
}


@dataclass
class ResourceFactory:
    data: Dict
    _env: env.Environment
    process_factory: process.ProcessFactory
    state_factory: state.StateFactory
    queue_factory: store.QueueFactory

    resources: List[Resource] = field(default_factory=list, init=False)
    controllers: List[control.Controller] = field(default_factory=list, init=False)

    def create_resources(self):
        for values in self.data.values():
            self.add_resource(values)

    def adjust_process_capacities(self, values: Dict):
        for process, capacity in zip(values['processes'], values['process_capacity']):
            values['processes'] += [process]*(capacity - 1)

    def add_queues_to_resource(self, _resource: Resource, values: Dict):
        if 'input_queues' in values.keys():
            input_queues = self.queue_factory.get_queues(values['input_queues'])
            _resource.add_input_queues(input_queues)
        if 'output_queues' in values.keys():
            output_queues = self.queue_factory.get_queues(values['output_queues'])
            _resource.add_output_queues(output_queues)


    def add_resource(self, values: Dict):
        states = self.state_factory.get_states(values['states'])
        if 'process_capacity' in values:
            self.adjust_process_capacities(values)
            
        processes = self.process_factory.get_processes_in_order(values['processes'])

        resource = ConcreteResource(ID=values['ID'],
                                    description=values['description'],
                                    location=values['location'],
                                    env=self._env,
                                    capacity=values['capacity'],
                                    processes=processes,
                                    )
        self.add_queues_to_resource(resource, values)

        register_states(resource, states, self._env)
        register_production_states_for_processes(resource, self.state_factory, self._env)
        self.resources.append(resource)


        controller_class = get_class_from_str(name=values['controller'], cls_dict=CONTROLLER_DICT)
        control_policy = get_class_from_str(name=values['control_policy'], cls_dict=CONTROL_POLICY_DICT)
        controller: control.Controller = controller_class(control_policy, self._env)
        controller.set_resource(resource)
        self.controllers.append(controller)

        resource.set_controller(controller)


    def start_resources(self):
        for _resource in self.resources:
            _resource.start_states()
            
        for controller in self.controllers:
            self._env.process(controller.control_loop())

    def get_resource(self, ID):
        return [st for st in self.resources if st.ID == ID].pop()

    def get_controller_of_resource(self, _resource: Resource) -> control.Controller:
        for controller in self.controllers:
            if controller._resource == _resource:
                return controller

    def get_resources(self, IDs: List[str]) -> List[Resource]:
        return [r for r in self.resources if r.ID in IDs]

    def get_resources_with_process(self, __process: process.Process) -> List[Resource]:
        return [r for r in self.resources if __process in r.processes]
