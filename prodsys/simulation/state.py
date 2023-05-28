from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Union, TYPE_CHECKING, Generator, List

from simpy import events
from simpy import exceptions
from pydantic import BaseModel, Extra, root_validator, Field

from prodsys.simulation import sim, time_model
from prodsys.data_structures.state_data import (
    StateData,
    BreakDownStateData,
    ProductionStateData,
    TransportStateData,
    SetupStateData,
    ProcessBreakDownStateData,
)

if TYPE_CHECKING:
    from prodsys.simulation import product, resources


class StateEnum(str, Enum):
    start_state = "start state"
    start_interrupt = "start interrupt"
    end_interrupt = "end interrupt"
    end_state = "end state"
    finished_product = "finished product"
    created_product = "created product"


class StateTypeEnum(str, Enum):
    production = "Production"
    transport = "Transport"
    breakdown = "Breakdown"
    process_breakdown = "ProcessBreakdown"
    setup = "Setup"
    source = "Source"
    sink = "Sink"


class StateInfo(BaseModel, extra=Extra.allow):
    ID: str
    resource_ID: str
    _event_time: Optional[float] = 0.0
    _expected_end_time: Optional[float] = 0.0
    _activity: Optional[StateEnum] = None
    _state_type: Optional[StateTypeEnum] = None
    _product_ID: str = ""
    _target_ID: str = ""

    def log_target_location(self, target: product.Location, state_type: StateTypeEnum):
        self._target_ID = target.data.ID
        self._state_type = state_type

    def log_product(self, _product: product.Product, state_type: StateTypeEnum):
        self._product_ID = _product.product_data.ID
        self._state_type = state_type

    def log_start_state(
        self, start_time: float, expected_end_time: float, state_type: StateTypeEnum
    ):
        self._event_time = start_time
        self._expected_end_time = expected_end_time
        self._activity = StateEnum.start_state
        self._state_type = state_type

    def log_start_interrupt_state(self, start_time: float, state_type: StateTypeEnum):
        self._event_time = start_time
        self._activity = StateEnum.start_interrupt
        self._state_type = state_type

    def log_end_interrupt_state(
        self, start_time: float, expected_end_time: float, state_type: StateTypeEnum
    ):
        self._event_time = start_time
        self._expected_end_time = expected_end_time
        self._activity = StateEnum.end_interrupt
        self._state_type = state_type

    def log_end_state(self, start_time: float, state_type: StateTypeEnum):
        self._event_time = start_time
        self._activity = StateEnum.end_state
        self._state_type = state_type


class State(ABC, BaseModel):
    state_data: StateData
    time_model: time_model.TimeModel
    env: sim.Environment
    active: events.Event = Field(default=None, init=False)
    finished_process: events.Event = Field(default=None, init=False)
    resource: resources.Resource = Field(init=False, default=None)
    process: Optional[events.Process] = Field(default=None)
    state_info: StateInfo = Field(None)

    class Config:
        arbitrary_types_allowed = True

    def set_resource(self, resource_model: resources.Resource) -> None:
        self.resource = resource_model
        self.state_info = StateInfo(
            ID=self.state_data.ID, resource_ID=self.resource.data.ID
        )

    def deactivate(self):
        """
        Deactivates the state by setting the active event to a new event which is not yet triggered.
        """
        self.active = events.Event(self.env)

    def activate(self):
        """
        Activates the state by triggering the active event.

        Raises:
            RuntimeError: If the state is allready active.
        """
        try:
            self.active.succeed()
        except:
            raise RuntimeError(f"state {self.state_data.ID} is allready succeded!!")

    @abstractmethod
    def process_state(self) -> Generator:
        pass

    @abstractmethod
    def interrupt_process(self) -> Generator:
        pass

    def activate_state(self):
        pass

    def prepare_for_run(self):
        pass


class ProductionState(State):
    state_data: ProductionStateData
    interrupt_processed: events.Event = Field(default=None, init=False)
    start: float = 0.0
    done_in: float = 0.0

    def prepare_for_run(self):
        # self.interrupt_processed = events.Event(self.env).succeed()
        self.finished_process = events.Event(self.env)

    def activate_state(self):
        self.interrupt_processed = events.Event(self.env).succeed()
        self.active = events.Event(self.env).succeed()

    def process_state(self) -> Generator:
        """Runs a single process of a resource.
        While making a part, the machine may break multiple times.
        Request a repairman when this happens.
        """
        self.done_in = self.time_model.get_next_time()
        try:
            yield events.AllOf(self.env, [self.resource.active, self.active])
        except exceptions.Interrupt:
            yield events.AllOf(self.env, [self.active, self.resource.active])
            self.interrupt_processed.succeed()
        self.state_info.log_start_state(
            self.env.now, self.env.now + self.done_in, StateTypeEnum.production
        )
        while self.done_in:
            try:
                self.start = self.env.now
                yield self.env.timeout(self.done_in)
                self.done_in = 0  # Set to 0 to exit while loop.

            except exceptions.Interrupt:
                self.state_info.log_start_interrupt_state(
                    self.env.now, StateTypeEnum.production
                )
                self.update_done_in()
                yield events.AllOf(self.env, [self.active, self.resource.active])
                self.interrupt_processed.succeed()
                self.state_info.log_end_interrupt_state(
                    self.env.now, self.env.now + self.done_in, StateTypeEnum.production
                )
        self.state_info.log_end_state(self.env.now, StateTypeEnum.production)
        # TODO: fix that processes are not started whilst others are interrupted so that the finished_process event is still unsucceded and only one process is running for each produtionstate
        self.finished_process.succeed()

    def update_done_in(self):
        self.done_in -= self.env.now - self.start  # How much time left?
        if self.done_in < 0:
            self.done_in = 0

    def interrupt_process(self) -> Generator:
        yield self.interrupt_processed
        if self.process and self.process.is_alive:
            self.interrupt_processed = events.Event(self.env)
            self.process.interrupt()


class TransportState(State):
    state_data: TransportStateData
    interrupt_processed: events.Event = Field(default=None, init=False)
    start: float = 0.0
    done_in: float = 0.0

    def prepare_for_run(self):
        # self.interrupt_processed = events.Event(self.env).succeed()
        self.finished_process = events.Event(self.env)

    def activate_state(self):
        self.interrupt_processed = events.Event(self.env).succeed()
        self.active = events.Event(self.env).succeed()

    def process_state(self, target: List[float]) -> Generator:
        """Runs a single process of a resource.
        While making a part, the machine may break multiple times.
        Request a repairman when this happens.
        """
        self.done_in = self.time_model.get_next_time(
            origin=self.resource.get_location(), target=target
        )
        try:
            yield events.AllOf(self.env, [self.resource.active, self.active])
        except exceptions.Interrupt:
            yield events.AllOf(self.env, [self.active, self.resource.active])
            self.interrupt_processed.succeed()
        self.state_info.log_start_state(
            self.env.now, self.env.now + self.done_in, StateTypeEnum.transport
        )
        while self.done_in:
            try:
                self.start = self.env.now
                yield self.env.timeout(self.done_in)
                self.done_in = 0  # Set to 0 to exit while loop.

            except exceptions.Interrupt:
                self.state_info.log_start_interrupt_state(
                    self.env.now, StateTypeEnum.transport
                )
                self.update_done_in()
                yield events.AllOf(self.env, [self.active, self.resource.active])
                self.interrupt_processed.succeed()
                self.state_info.log_end_interrupt_state(
                    self.env.now, self.env.now + self.done_in, StateTypeEnum.transport
                )
        self.resource.location = target
        self.state_info.log_end_state(self.env.now, StateTypeEnum.transport)
        self.finished_process.succeed()

    def update_done_in(self):
        self.done_in -= self.env.now - self.start  # How much time left?
        if self.done_in < 0:
            self.done_in = 0

    def interrupt_process(self) -> Generator:
        yield self.interrupt_processed
        if self.process and self.process.is_alive:
            self.interrupt_processed = events.Event(self.env)
            self.process.interrupt()


class BreakDownState(State):
    state_data: BreakDownStateData
    repair_time_model: time_model.TimeModel

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
            self.state_info.log_start_state(
                self.env.now, self.env.now + 15, StateTypeEnum.breakdown
            )
            yield self.env.timeout(self.repair_time_model.get_next_time())
            self.resource.activate()
            self.state_info.log_end_state(self.env.now, StateTypeEnum.breakdown)

    def wait_for_breakdown(self):
        yield self.env.timeout(self.time_model.get_next_time())

    def interrupt_process(self) -> Generator:
        while True:
            yield None


class ProcessBreakDownState(State):
    state_data: ProcessBreakDownStateData
    production_states: List[State] = None
    repair_time_model: time_model.TimeModel

    @root_validator
    def post_init(cls, values):
        values["active"] = events.Event(values["env"])
        return values

    def set_production_states(self, production_states: List[ProductionState]):
        if any(
            [
                production_state.state_data.ID != self.state_data.process_id
                for production_state in production_states
            ]
        ):
            raise ValueError(
                f"Production states {production_states} do not match process id {self.state_data.process_id}"
            )
        self.production_states = production_states

    def process_state(self) -> Generator:
        while True:
            yield self.env.process(self.wait_for_breakdown())
            yield events.AllOf(
                self.env, [state.active for state in self.production_states]
            )
            for state in self.production_states + self.resource.setup_states:
                state.deactivate()
            interrupt_events = []
            for state in self.production_states:
                if state.process and state.process.is_alive:
                    interrupt_events.append(self.env.process(state.interrupt_process()))
            interrupt_events += [
                self.env.process(state.interrupt_process())
                for state in self.resource.setup_states
            ]
            yield self.env.all_of(interrupt_events)
            self.state_info.log_start_state(
                self.env.now, self.env.now + 5, StateTypeEnum.process_breakdown
            )
            yield self.env.timeout(self.repair_time_model.get_next_time())
            self.state_info.log_end_state(self.env.now, StateTypeEnum.process_breakdown)
            yield self.resource.active
            for state in self.production_states + self.resource.setup_states:
                state.activate()

    def wait_for_breakdown(self):
        yield self.env.timeout(self.time_model.get_next_time())

    def interrupt_process(self) -> Generator:
        while True:
            yield None


class SetupState(State):
    state_data: SetupStateData
    start: float = 0.0
    done_in: float = 0.0
    interrupt_processed: events.Event = Field(default=None, init=False)

    @property
    def is_active(self):
        return events.AllOf(self.env, [self.active, self.resource.active])

    def prepare_for_run(self):
        self.finished_process = events.Event(self.env)

    def activate_state(self):
        self.interrupt_processed = events.Event(self.env).succeed()
        self.active = events.Event(self.env).succeed()

    def process_state(self) -> Generator:
        self.done_in = self.time_model.get_next_time()
        try:
            yield self.is_active
            running_processes = [
                state.process
                for state in self.resource.production_states
                if (state.process and state.process.is_alive)
            ]
            yield events.AllOf(self.env, running_processes)
        except exceptions.Interrupt:
            yield self.is_active
            self.interrupt_processed.succeed()
            running_processes = [
                state.process
                for state in self.resource.production_states
                if (state.process and state.process.is_alive)
            ]
            yield events.AllOf(self.env, running_processes)

        self.state_info.log_start_state(
            self.env.now, self.env.now + self.done_in, StateTypeEnum.setup
        )
        while self.done_in:
            try:
                self.start = self.env.now
                yield self.env.timeout(self.done_in)
                self.done_in = 0
            except exceptions.Interrupt:
                self.state_info.log_start_interrupt_state(
                    self.env.now, StateTypeEnum.setup
                )
                self.update_done_in()
                yield events.AllOf(self.env, [self.active, self.resource.active])
                self.interrupt_processed.succeed()
                self.state_info.log_end_interrupt_state(
                    self.env.now, self.env.now + self.done_in, StateTypeEnum.setup
                )
        self.state_info.log_end_state(self.env.now, StateTypeEnum.setup)
        self.finished_process.succeed()

    def update_done_in(self):
        self.done_in -= self.env.now - self.start  # How much time left?
        if self.done_in < 0:
            self.done_in = 0

    def interrupt_process(self) -> Generator:
        yield self.interrupt_processed
        if self.process and self.process.is_alive:
            self.interrupt_processed = events.Event(self.env)
            self.process.interrupt()


STATE_UNION = Union[
    BreakDownState, ProductionState, TransportState, SetupState, ProcessBreakDownState
]
