from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Union, TYPE_CHECKING, Generator, Tuple

from simpy import events
from simpy import exceptions
from pydantic import BaseModel, Extra, root_validator, Field

from prodsim.simulation import sim, time_model
from prodsim.data_structures.state_data import (
    StateData,
    BreakDownStateData,
    ProductionStateData,
    TransportStateData,
)

if TYPE_CHECKING:
    from prodsim.simulation import material, resources


class StateEnum(str, Enum):
    start_state = "start state"
    start_interrupt = "start interrupt"
    end_interrupt = "end interrupt"
    end_state = "end state"


class StateInfo(BaseModel, extra=Extra.allow):
    ID: str
    resource_ID: str
    _event_time: Optional[float] = 0.0
    _expected_end_time: Optional[float] = 0.0
    _activity: Optional[StateEnum] = None
    _material_ID: str = ""
    _target_ID: str = ""

    def log_target_location(self, target: material.Location):
        self._target_ID = target.data.ID

    def log_material(self, _material: material.Material):
        self._material_ID = _material.material_data.ID

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


class State(ABC, BaseModel):
    state_data: StateData
    time_model: time_model.TimeModel
    env: sim.Environment
    active: events.Event = Field(None, description="active", init=False)
    finished_process: events.Event = Field(
        None, description="finished_process", init=False
    )
    resource: resources.Resourcex = Field(
        init=False, default=None, description="_resource"
    )
    process: Optional[events.Process] = Field(None, description="process")
    state_info: StateInfo = Field(None, description="state_info")

    class Config:
        arbitrary_types_allowed = True

    def set_resource(self, resource_model: resources.Resourcex) -> None:
        self.resource = resource_model
        self.finished_process = events.Event(self.env).succeed()
        self.state_info = StateInfo(
            ID=self.state_data.ID, resource_ID=self.resource.data.ID
        )

    def activate(self):
        try:
            self.active.succeed()
        except:
            raise RuntimeError("state is allready succeded!!")
        self.active = events.Event(self.env)

    @abstractmethod
    def process_state(self) -> Generator:
        pass

    @abstractmethod
    def interrupt_process(self) -> Generator:
        pass

    def activate_state(self):
        pass


class ProductionState(State):
    state_data: ProductionStateData
    interrupt_processed: events.Event = Field(
        None, description="interrupt_processed", init=False
    )
    start: float = 0.0
    done_in: float = 0.0

    def activate_state(self):
        self.interrupt_processed = events.Event(self.env).succeed()
        self.active = events.Event(self.env)
        self.finished_process = events.Event(self.env)

    def process_state(self) -> Generator:
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
                self.state_info.log_end_interrupt_state(
                    self.env.now, self.env.now + self.done_in
                )
        self.state_info.log_end_state(self.env.now)
        self.finished_process.succeed()

    def update_done_in(self):
        self.done_in -= self.env.now - self.start  # How much time left?
        if self.done_in < 0:
            self.done_in = 0

    def interrupt_process(self) -> Generator:
        yield self.interrupt_processed
        self.interrupt_processed = events.Event(self.env)
        if self.process and self.process.is_alive:
            self.process.interrupt()


class TransportState(State):
    state_data: TransportStateData
    interrupt_processed: events.Event = Field(
        None, description="interrupt_processed", init=False
    )
    start: float = 0.0
    done_in: float = 0.0

    def activate_state(self):
        self.interrupt_processed = events.Event(self.env).succeed()
        self.active = events.Event(self.env)
        self.finished_process = events.Event(self.env)

    def process_state(self, target: Tuple[float, float]) -> Generator:
        """Runs a single process of a resource.
        While making a part, the machine may break multiple times.
        Request a repairman when this happens.
        """
        self.done_in = self.time_model.get_next_time(
            origin=self.resource.get_location(), target=target
        )
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
                self.state_info.log_end_interrupt_state(
                    self.env.now, self.env.now + self.done_in
                )
        self.resource.location = target
        self.state_info.log_end_state(self.env.now)
        self.finished_process.succeed()

    def update_done_in(self):
        self.done_in -= self.env.now - self.start  # How much time left?
        if self.done_in < 0:
            self.done_in = 0

    def interrupt_process(self) -> Generator:
        yield self.interrupt_processed
        self.interrupt_processed = events.Event(self.env)
        if self.process and self.process.is_alive:
            self.process.interrupt()


class BreakDownState(State):
    state_data: BreakDownStateData

    def __post_init__(self):
        self.active = events.Event(self.env)

    @root_validator
    def post_init(cls, values):
        values["active"] = events.Event(values["env"])
        return values

    def process_state(self) -> Generator:
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

    def interrupt_process(self) -> Generator:
        while True:
            yield None


class ScheduledState(State):
    def __post_init__(self):
        self.active = events.Event(self.env)
        # self.process = self.env.process(self.process_state())

    def process_state(self) -> Generator:
        while True:
            yield None

    def wait_for_schedule(self):
        pass

    def interrupt_process(self) -> Generator:
        while True:
            yield None


class SetupState(ScheduledState):
    def __post_init__(self):
        self.active = events.Event(self.env)
        # self.process = self.env.process(self.process_state())

    def process_state(self) -> Generator:
        while True:
            yield None

    def wait_for_schedule(self):
        pass

    def interrupt_process(self) -> Generator:
        while True:
            yield None


STATE_UNION = Union[BreakDownState, ProductionState, TransportState]
