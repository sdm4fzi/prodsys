from __future__ import annotations

from abc import ABC
from typing import List, Generator, Optional, Union, Tuple, TYPE_CHECKING, Any

from pydantic import BaseModel, Field, Extra
import random

from simpy.resources import resource
from simpy import events
from prodsim.simulation import process, sim, store


from prodsim.data_structures.resource_data import RESOURCE_DATA_UNION, ProductionResourceData, TransportResourceData
from prodsim.simulation import control, state
from prodsim.util import util

class Resourcex(BaseModel, ABC, resource.Resource):
    env: sim.Environment
    data: RESOURCE_DATA_UNION    
    processes: List[process.PROCESS_UNION]
    controller: control.Controller

    states: List[state.State] = Field(default_factory=list, init=False)
    production_states: List[state.State] = Field(default_factory=list, init=False)
    setup_states: List[state.SetupState] = Field(default_factory=list, init=False)

    available: events.Event = Field(default=None, init=False)
    active: events.Event = Field(default=None, init=False)
    current_process: process.PROCESS_UNION = Field(default=None, init=False)

    class Config:
        arbitrary_types_allowed = True
        extra=Extra.allow


    def get_controller(self) -> control.Controller:
        return self.controller

    def add_state(self, input_state: state.STATE_UNION) -> None:
        if isinstance(input_state, state.SetupState):
            self.setup_states.append(input_state)
        else:
            self.states.append(input_state)
        input_state.set_resource(self)

    def add_production_state(self, input_state: state.ProductionState) -> None:
        self.production_states.append(input_state)
        input_state.set_resource(self)

    def start_states(self):
        resource.Resource.__init__(self, self.env, capacity=self.data.capacity)
        self.available = events.Event(self.env)
        self.active = events.Event(self.env).succeed()
        for actual_state in self.states:
            actual_state.activate_state()
            actual_state.process = self.env.process(actual_state.process_state())

    def get_process(self, process: process.PROCESS_UNION) -> state.State:
        possible_states = [actual_state for actual_state in self.production_states if actual_state.state_data.ID == process.process_data.ID]
        if not possible_states:
            raise ValueError(f"Process {process.process_data.ID} not found in resource {self.data.ID}")
        return random.choice(possible_states)

    def get_free_process(self, process: process.PROCESS_UNION) -> Optional[state.State]:
        for actual_state in self.production_states:
            if actual_state.state_data.ID == process.process_data.ID and actual_state.process is None:
                return actual_state
        return None

    def get_location(self) -> Tuple[float, float]:
        return self.data.location

    def set_location(self, new_location: Tuple[float, float]) -> None:
        self.data.location = new_location

    def get_states(self) -> List[state.State]:
        return self.states

    def activate(self):
        self.active.succeed()
        for actual_state in self.production_states:
            if (isinstance(actual_state, state.ProductionState) or isinstance(actual_state, state.TransportState) or isinstance(actual_state, state.SetupStateData)) and actual_state.process is not None:
                actual_state.activate()

    def request_repair(self):
        pass

    def reactivate(self):
        for _state in self.states:
            _state.activate()

    def interrupt_states(self) -> Generator:
        eventss: List[events.Event] = []
        for state in self.production_states:
            if state.process:
                eventss.append(self.env.process(state.interrupt_process()))
        yield events.AllOf(self.env, eventss)

    def setup(self, _process: process.PROCESS_UNION):
        if self.current_process is None:
            self.current_process = _process
            return self.env.process(util.trivial_process(self.env))
        for input_state in self.setup_states:
            if input_state.state_data.target_setup == _process.process_data.ID and \
            input_state.state_data.origin_setup == self.current_process.process_data.ID:
                self.current_process = _process
                input_state.process = self.env.process(input_state.process_state())
                return input_state.process
        else:
            return self.env.process(util.trivial_process(self.env))


class ProductionResource(Resourcex):
    data: ProductionResourceData
    controller: control.ProductionController

    input_queues: List[store.Queue] = []
    output_queues: List[store.Queue] = []

    def add_input_queues(self, input_queues: List[store.Queue]):
        self.input_queues.extend(input_queues)

    def add_output_queues(self, output_queues: List[store.Queue]):
        self.output_queues.extend(output_queues)

class TransportResource(Resourcex):
    data: TransportResourceData
    controller: control.TransportController


RESOURCE_UNION = Union[ProductionResource, TransportResource]