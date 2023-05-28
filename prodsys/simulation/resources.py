from __future__ import annotations

from abc import ABC
from typing import List, Generator, Optional, Union

from pydantic import BaseModel, Field, Extra
import random

from simpy.resources import resource
from simpy import events
from prodsys.simulation import process, sim, store


from prodsys.data_structures.resource_data import (
    RESOURCE_DATA_UNION,
    ProductionResourceData,
    TransportResourceData,
)
from prodsys.simulation import control, state
from prodsys.util import util


class Resource(BaseModel, ABC, resource.Resource):
    env: sim.Environment
    data: RESOURCE_DATA_UNION
    processes: List[process.PROCESS_UNION]
    controller: control.Controller

    states: List[state.State] = Field(default_factory=list, init=False)
    production_states: List[state.State] = Field(default_factory=list, init=False)
    setup_states: List[state.SetupState] = Field(default_factory=list, init=False)

    got_free: events.Event = Field(default=None, init=False)
    active: events.Event = Field(default=None, init=False)
    current_setup: process.PROCESS_UNION = Field(default=None, init=False)
    reserved_setup: process.PROCESS_UNION = Field(default=None, init=False)
    _pending_put: int = 0

    class Config:
        arbitrary_types_allowed = True
        extra = Extra.allow

    @property
    def capacity_current_setup(self) -> int:
        if not self.current_setup and not self.reserved_setup:
            return self.capacity
        elif (
            self.reserved_setup
            and self.current_setup.process_data.ID
            != self.reserved_setup.process_data.ID
        ):
            current_setup_ID = self.reserved_setup.process_data.ID
        elif self.current_setup:
            current_setup_ID = self.current_setup.process_data.ID
        length = len(
            [
                state
                for state in self.production_states
                if state.state_data.ID == current_setup_ID
            ]
        )
        return length

    def reserve_setup(self, process: process.PROCESS_UNION) -> None:
        self.reserved_setup = process

    def unreserve_setup(self) -> None:
        self.reserved_setup = None

    @property
    def in_setup(self) -> bool:
        return self.reserved_setup is not None

    @property
    def full(self) -> bool:
        if self.in_setup:
            return True
        return (
            self.capacity_current_setup
            - self._pending_put
            - len(self.controller.running_processes)
        ) <= 0

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
        self.active = events.Event(self.env).succeed()
        self.got_free = events.Event(self.env)
        for actual_state in self.states + self.production_states + self.setup_states:
            actual_state.activate_state()
        for actual_state in self.states:
            actual_state.process = self.env.process(actual_state.process_state())

    def get_process(self, process: process.PROCESS_UNION) -> state.State:
        possible_states = [
            actual_state
            for actual_state in self.production_states
            if actual_state.state_data.ID == process.process_data.ID
        ]
        if not possible_states:
            raise ValueError(
                f"Process {process.process_data.ID} not found in resource {self.data.ID}"
            )
        return random.choice(possible_states)

    def get_processes(self, process: process.PROCESS_UNION) -> List[state.State]:
        possible_states = [
            actual_state
            for actual_state in self.production_states
            if actual_state.state_data.ID == process.process_data.ID
        ]
        if not possible_states:
            raise ValueError(
                f"Process {process.process_data.ID} not found in resource {self.data.ID}"
            )
        return possible_states

    def get_free_process(self, process: process.PROCESS_UNION) -> Optional[state.State]:
        for actual_state in self.production_states:
            if actual_state.state_data.ID == process.process_data.ID and (
                actual_state.process is None or not actual_state.process.is_alive
            ):
                return actual_state
        return None

    def get_location(self) -> List[float]:
        return self.data.location

    def set_location(self, new_location: List[float]) -> None:
        self.data.location = new_location

    def get_states(self) -> List[state.State]:
        return self.states

    def activate(self):
        self.active.succeed()

    def request_repair(self):
        pass

    def interrupt_states(self) -> Generator:
        eventss: List[events.Event] = []
        for state in self.setup_states + self.production_states:
            if state.process and state.interrupt_processed.triggered:
                eventss.append(self.env.process(state.interrupt_process()))
        yield events.AllOf(self.env, eventss)

    def get_free_of_setups(self) -> Generator:
        running_setups = [
            state.process
            for state in self.setup_states
            if (state.process and state.process.is_alive)
        ]
        yield events.AllOf(self.env, running_setups)

    def get_free_of_processes_in_preparation(self) -> Generator:
        running_processes = [
            state.process
            for state in self.production_states
            if (state.process and state.process.is_alive)
        ]
        yield events.AllOf(self.env, running_processes)

    def setup(self, _process: process.PROCESS_UNION):
        if self.current_setup is None:
            yield self.env.process(util.trivial_process(self.env))
            self.current_setup = _process
            return
        if self.reserved_setup:
            setup_to_compare = self.reserved_setup
        else:
            setup_to_compare = self.current_setup

        if setup_to_compare.process_data.ID == _process.process_data.ID:
            yield self.env.process(self.get_free_of_setups())
            yield self.env.process(util.trivial_process(self.env))
            return

        for input_state in self.setup_states:
            if (
                input_state.state_data.target_setup == _process.process_data.ID
                and input_state.state_data.origin_setup
                == setup_to_compare.process_data.ID
            ):
                self.reserve_setup(_process)
                yield self.env.process(self.get_free_of_setups())
                input_state.prepare_for_run()
                input_state.process = self.env.process(input_state.process_state())
                yield input_state.process
                input_state.process = None
                self.current_setup = _process
                self.unreserve_setup()

        else:
            yield self.env.process(self.get_free_of_setups())
            yield self.env.process(util.trivial_process(self.env))


class ProductionResource(Resource):
    data: ProductionResourceData
    controller: control.ProductionController

    input_queues: List[store.Queue] = []
    output_queues: List[store.Queue] = []
    pending_: int = []

    def add_input_queues(self, input_queues: List[store.Queue]):
        self.input_queues.extend(input_queues)

    def add_output_queues(self, output_queues: List[store.Queue]):
        self.output_queues.extend(output_queues)

    def reserve_input_queues(self):
        for input_queue in self.input_queues:
            input_queue.reserve()

    def unreserve_input_queues(self):
        for input_queue in self.input_queues:
            input_queue.unreseve()


class TransportResource(Resource):
    data: TransportResourceData
    controller: control.TransportController


RESOURCE_UNION = Union[ProductionResource, TransportResource]
