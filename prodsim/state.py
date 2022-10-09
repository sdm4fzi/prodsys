from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from pydantic import BaseModel, Extra
from dataclasses import dataclass, field
from typing import List, Type, Optional, Union, Literal

import simpy
from . import env
from . import resources
from . import time_model
from . import base
from .util import get_class_from_str
from . import material

class StateEnum(str, Enum):
    start_state: str = "start state"
    start_interrupt: str = "start interrupt"
    end_interrupt: str = "end interrupt"
    end_state: str = "end state"

class StateInfo(BaseModel, extra=Extra.allow):
    ID: str
    resource_ID: str
    _event_time: float = None
    _expected_end_time: float  = None
    _activity: StateEnum = None
    _material_ID: str  = None
    _target_ID: str = None

    def log_target_location(self, target: resources.Resource):
        self._target_ID = target.ID

    def log_material(self, _material: material.Material):
        self._material_ID = _material.ID

    def log_start_state(self, start_time: float, expected_end_time: float):
        self._event_time = start_time
        self._expected_end_time = expected_end_time
        self._activity = StateEnum.start_state

    def log_start_interrupt_state(self, start_time: float):
        self._event_time = start_time
        self._activity = StateEnum.start_interrupt

    def log_end_interrupt_state(self, start_time: float, expected_end_time: float):
        self._event_time = start_time
        self._expected_end_time = expected_end_time
        self._activity = StateEnum.end_interrupt

    def log_end_state(self, start_time: float):
        self._event_time = start_time
        self._activity = StateEnum.end_state

@dataclass
class State(ABC, base.IDEntity):
    env: env.Environment
    time_model: time_model.TimeModel
    active: simpy.Event = field(default=None, init=False)
    finished_process: simpy.Event = field(default=None, init=False)
    _resource: resources.Resource = field(default=None, init=False)
    process: simpy.Process = field(default=None, init=False)
    state_info: StateInfo = field(default=None, init=False)

    @property
    def resource(self) -> resources.Resource:
        return self._resource


    @resource.setter
    def resource(self, resource_model: resources.Resource) -> None:
        self._resource = resource_model
        self.finished_process = simpy.Event(self.env).succeed()
        self.state_info = StateInfo(ID=self.ID, resource_ID=self._resource.ID)


    def activate(self):
        try:
            self.active.succeed()
        except:
            raise RuntimeError("state is allready succeded!!")
        self.active = simpy.Event(self.env)

    @abstractmethod
    def __post_init__(self):
        pass

    @abstractmethod
    def process_state(self):
        pass

    @abstractmethod
    def interrupt_process(self):
        pass

    def activate_state(self):
        pass


class ProductionState(State):
    interrupt_processed: simpy.Event
    start: float
    done_in: float

    def __post_init__(self):
        self.start = 0.0
        self.done_in = 0.0

    def activate_state(self):
        self.interrupt_processed = simpy.Event(self.env).succeed()
        self.active = simpy.Event(self.env)
        self.finished_process = simpy.Event(self.env)

    def process_state(self):
        """Runs a single process of a resource.
        While making a part, the machine may break multiple times.
        Request a repairman when this happens.
        """
        self.done_in = self.time_model.get_next_time()
        yield self.resource.active
        self.state_info.log_start_state(self.env.now, self.env.now + self.done_in)
        while self.done_in:
            try:
                self.start = self.env.now
                yield self.env.timeout(self.done_in)
                self.done_in = 0  # Set to 0 to exit while loop.

            except simpy.Interrupt:
                self.state_info.log_start_interrupt_state(self.env.now)
                self.update_done_in()
                yield self.active
                self.interrupt_processed.succeed()
                self.state_info.log_end_interrupt_state(self.env.now, self.env.now + self.done_in)
        # TODO: parts made has to be moved to product or logger class
        self.resource.parts_made += 1
        self.state_info.log_end_state(self.env.now)
        self.finished_process.succeed()


    def update_done_in(self):
        self.done_in -= self.env.now - self.start  # How much time left?
        if self.done_in < 0:
            self.done_in = 0

    def interrupt_process(self):
        yield self.interrupt_processed
        self.interrupt_processed = simpy.Event(self.env)
        if self.process.is_alive:
            self.process.interrupt()


class TransportState(State):
    interrupt_processed: simpy.Event
    start: float
    done_in: float

    def __post_init__(self):
        self.start = 0.0
        self.done_in = 0.0

    def activate_state(self):
        self.interrupt_processed = simpy.Event(self.env).succeed()
        self.active = simpy.Event(self.env)
        self.finished_process = simpy.Event(self.env)

    def process_state(self, target: List[float]):
        """Runs a single process of a resource.
        While making a part, the machine may break multiple times.
        Request a repairman when this happens.
        """
        self.done_in = self.time_model.get_next_time(origin=self.resource.get_location(), target=target)
        yield self.resource.active
        self.state_info.log_start_state(self.env.now, self.env.now + self.done_in)
        while self.done_in:
            try:
                self.start = self.env.now
                yield self.env.timeout(self.done_in)
                self.done_in = 0  # Set to 0 to exit while loop.

            except simpy.Interrupt:
                self.state_info.log_start_interrupt_state(self.env.now)
                self.update_done_in()
                yield self.active
                self.interrupt_processed.succeed()
                self.state_info.log_end_interrupt_state(self.env.now, self.env.now + self.done_in)
        # TODO: parts made has to be moved to product or logger class
        self.resource.location = target
        self.resource.parts_made += 1
        self.state_info.log_end_state(self.env.now)
        self.finished_process.succeed()

    def update_done_in(self):
        self.done_in -= self.env.now - self.start  # How much time left?
        if self.done_in < 0:
            self.done_in = 0

    def interrupt_process(self):
        yield self.interrupt_processed
        self.interrupt_processed = simpy.Event(self.env)
        if self.process.is_alive:
            self.process.interrupt()


class BreakDownState(State):

    def __post_init__(self):
        self.active = simpy.Event(self.env)

    def process_state(self):
        while True:
            yield self.env.process(self.wait_for_breakdown())
            yield self.resource.active
            self.resource.active = simpy.Event(self.env)
            yield self.env.process(self.resource.interrupt_states())
            self.state_info.log_start_state(self.env.now, self.env.now + 15)
            # TODO: Schedule here the maintainer! or a time model for a repair
            yield self.env.timeout(15)
            self.resource.activate()
            self.state_info.log_end_state(self.env.now)

    def wait_for_breakdown(self):
        yield self.env.timeout(self.time_model.get_next_time())

    def interrupt_process(self):
        pass


class ScheduledState(State):

    def __post_init__(self):
        self.active = simpy.Event(self.env)
        # self.process = self.env.process(self.process_state())

    def process_state(self):
        pass

    def wait_for_schedule(self):
        pass

    def interrupt_process(self):
        pass


STATE_DICT: dict = {
    'ProductionState': ProductionState,
    'TransportState': TransportState,
    'BreakDownState': BreakDownState,
}


@dataclass
class StateFactory:
    data: dict
    env: env.Environment
    time_model_factory: time_model.TimeModelFactory

    states: List[State] = field(default_factory=list)

    def create_states(self):
        for cls_name, items in self.data.items():
            cls: Type[State] = get_class_from_str(cls_name, STATE_DICT)
            for values in items.values():
                self.add_states(cls, values)

    def add_states(self, cls: Type[State], values):
        time_model = self.time_model_factory.get_time_model(values['time_model_id'])
        self.states.append(cls(env=self.env,
                               time_model=time_model,
                               ID=values['ID'],
                               description=values['description']
                               ))

    def get_states(self, IDs: List[str]) -> List[State]:
        return [st for st in self.states if st.ID in IDs]

