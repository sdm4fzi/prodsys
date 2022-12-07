from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import field
from enum import Enum
from typing import List, Optional, Union, TYPE_CHECKING

from simpy import events
from simpy import exceptions
from pydantic import BaseModel, Extra, root_validator, Field

from . import time_model, env
from .data_structures.state_data import StateData, BreakDownStateData, ProductionStateData, TransportStateData

if TYPE_CHECKING:
    from . import material, resources

class StateEnum(str, Enum):
    start_state = "start state"
    start_interrupt = "start interrupt"
    end_interrupt = "end interrupt"
    end_state = "end state"

class StateInfo(BaseModel, extra=Extra.allow):
    ID: str
    resource_ID: str
    _event_time: Optional[float] = 0.0
    _expected_end_time: Optional[float]  = 0.0
    _activity: Optional[StateEnum] = None
    _material_ID: str  = ""
    _target_ID: str = ""

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

STATE_DATA_UNION = Union[BreakDownStateData, ProductionStateData, TransportStateData]

class State(ABC, BaseModel):
    state_data: StateData
    time_model: time_model.TimeModel
    env: env.Environment
    active: events.Event = Field(None, description='active', init=False)
    finished_process: events.Event = Field(None, description='finished_process', init=False)
    _resource: resources.Resource = Field(None, description='_resource')
    process: events.Process = Field(None, description='process')
    state_info: StateInfo = Field(None, description='state_info')

    class Config:
        arbitrary_types_allowed = True

    @property
    def resource(self) -> resources.Resource:
        return self._resource


    @resource.setter
    def resource(self, resource_model: resources.Resource) -> None:
        self._resource = resource_model
        self.finished_process = events.Event(self.env).succeed()
        self.state_info = StateInfo(ID=self.state_data.ID, resource_ID=self._resource.ID)


    def activate(self):
        try:
            self.active.succeed()
        except:
            raise RuntimeError("state is allready succeded!!")
        self.active = events.Event(self.env)

    @abstractmethod
    def process_state(self):
        pass

    @abstractmethod
    def interrupt_process(self):
        pass

    def activate_state(self):
        pass


class ProductionState(State):
    state_data: ProductionStateData
    interrupt_processed: events.Event
    start: float
    done_in: float

    @root_validator
    def post_init(cls, values):
        values["start"] = 0.0
        values["done_in"] = 0.0
        return values

    def activate_state(self):
        self.interrupt_processed = events.Event(self.env).succeed()
        self.active = events.Event(self.env)
        self.finished_process = events.Event(self.env)

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

            except exceptions.Interrupt:
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
        self.interrupt_processed = events.Event(self.env)
        if self.process.is_alive:
            self.process.interrupt()


class TransportState(State):
    state_data: TransportStateData
    interrupt_processed: events.Event
    start: float
    done_in: float

    @root_validator
    def post_init(cls, values):
        values["start"] = 0.0
        values["done_in"] = 0.0
        return values

    def activate_state(self):
        self.interrupt_processed = events.Event(self.env).succeed()
        self.active = events.Event(self.env)
        self.finished_process = events.Event(self.env)

    def process_state(self, target: List[float]):
        """Runs a single process of a resource.
        While making a part, the machine may break multiple times.
        Request a repairman when this happens.
        """
        self.done_in = self.time_model.get_next_time(origin=tuple(self.resource.get_location()), target=tuple(target))
        yield self.resource.active
        self.state_info.log_start_state(self.env.now, self.env.now + self.done_in)
        while self.done_in:
            try:
                self.start = self.env.now
                yield self.env.timeout(self.done_in)
                self.done_in = 0  # Set to 0 to exit while loop.

            except exceptions.Interrupt:
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
        self.interrupt_processed = events.Event(self.env)
        if self.process.is_alive:
            self.process.interrupt()


class BreakDownState(State):
    state_data: BreakDownStateData

    def __post_init__(self):
        self.active = events.Event(self.env)

    @root_validator
    def post_init(cls, values):
        values["active"] = events.Event(values["env"])
        return values

    def process_state(self):
        while True:
            yield self.env.process(self.wait_for_breakdown())
            yield self.resource.active
            self.resource.active = events.Event(self.env)
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
        self.active = events.Event(self.env)
        # self.process = self.env.process(self.process_state())

    def process_state(self):
        pass

    def wait_for_schedule(self):
        pass

    def interrupt_process(self):
        pass


STATE_UNION = Union[BreakDownState, ProductionState, TransportState]

