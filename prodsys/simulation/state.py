from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Union, TYPE_CHECKING, Generator, List

import logging
logger = logging.getLogger(__name__)

from simpy import events
from simpy import exceptions
from pydantic import BaseModel, ConfigDict, model_validator, Field

from prodsys.simulation import sim, time_model
from prodsys.models.state_data import (
    StateData,
    BreakDownStateData,
    ProductionStateData,
    TransportStateData,
    SetupStateData,
    ProcessBreakDownStateData,
)

if TYPE_CHECKING:
    from prodsys.simulation import product, resources, auxiliary


class StateEnum(str, Enum):
    """
    Enum for the different types a state can be in.
    """
    start_state = "start state"
    start_interrupt = "start interrupt"
    end_interrupt = "end interrupt"
    end_state = "end state"

    created_product = "created product"
    started_product_processing = "started product processing"
    # TODO: maybe rename finished_product to finished_product_processing for consistency
    finished_product = "finished product"

    created_auxiliary = "created auxiliary"
    started_auxiliary_usage = "started auxiliary usage"
    finished_auxiliary_usage = "finished auxiliary usage"


class StateTypeEnum(str, Enum):
    """
    Enum for the different types of states.
    """
    production = "Production"
    transport = "Transport"
    breakdown = "Breakdown"
    process_breakdown = "ProcessBreakdown"
    setup = "Setup"
    source = "Source"
    sink = "Sink"
    store = "Store"


class StateInfo(BaseModel):
    """
    Class that represents the current event information of a state while simulating.

    Args:
        ID (str): The ID of the state.
        resource_ID (str): The ID of the resource the state belongs to.
        _event_time (Optional[float], optional): The time of the event. Defaults to 0.0.
        _expected_end_time (Optional[float], optional): The expected end time of the state. Defaults to 0.0.
        _activity (Optional[StateEnum], optional): The activity of the state. Defaults to None.
        _state_type (Optional[StateTypeEnum], optional): The type of the state. Defaults to None.
        _product_ID (str, optional): The ID of the product the state belongs to. Defaults to "".
        _target_ID (str, optional): The ID of the target the state belongs to. Defaults to "".
    """
    ID: str
    resource_ID: str
    _event_time: Optional[float] = 0.0
    _expected_end_time: Optional[float] = 0.0
    _activity: Optional[StateEnum] = None
    _state_type: Optional[StateTypeEnum] = None
    _product_ID: str = ""
    _target_ID: str = ""
    _origin_ID: str = ""
    _empty_transport: Optional[bool] = None

    model_config=ConfigDict(extra="allow")

    def log_transport(self, origin: Optional[product.Locatable], target: product.Locatable, state_type: StateTypeEnum, empty_transport: bool):
        """
        Logs the target location of a transport state.

        Args:
            origin (Optional[product.Locatable]): The origin location, either a resource, source, node or a sink.
            target (product.Locatable): The target location, either a resource, source, node or a sink.
            state_type (StateTypeEnum): The type of the state.
            empty_transport (bool): Indicates if the transport is empty.
        """
        if not origin:
            self._origin_ID = "Loading station"
        else:
            self._origin_ID = origin.data.ID
        self._target_ID = target.data.ID
        self._state_type = state_type
        self._empty_transport = empty_transport

    def log_product(self, _product: product.Product, state_type: StateTypeEnum):
        """
        Logs the product of a transport or production state.

        Args:
            _product (product.Product): The product.
            state_type (StateTypeEnum): The type of the state.
        """
        self._product_ID = _product.product_data.ID
        self._state_type = state_type

    def log_auxiliary(self, _auxiliary: auxiliary.Auxiliary, state_type: StateTypeEnum):
        """
        Logs the product of a transport or production state.

        Args:
            _product (product.Product): The product.
            state_type (StateTypeEnum): The type of the state.
        """
        self._product_ID = _auxiliary.data.ID
        self._state_type = state_type

    def log_start_state(
        self, start_time: float, expected_end_time: float, state_type: StateTypeEnum
    ):
        """
        Logs the start of a state.

        Args:
            start_time (float): The start time of the state.
            expected_end_time (float): The expected end time of the state.
            state_type (StateTypeEnum): The type of the state.
        """
        self._event_time = start_time
        self._expected_end_time = expected_end_time
        self._activity = StateEnum.start_state
        self._state_type = state_type

    def log_start_interrupt_state(self, start_time: float, state_type: StateTypeEnum):
        """
        Logs the start of an interrupt of a state.

        Args:
            start_time (float): The start time of the interruption.
            state_type (StateTypeEnum): The type of the state.
        """
        self._event_time = start_time
        self._activity = StateEnum.start_interrupt
        self._state_type = state_type

    def log_end_interrupt_state(
        self, end_time: float, expected_end_time: float, state_type: StateTypeEnum
    ):
        """
        Logs the end of an interrupt of a state.

        Args:
            end_time (float): The end time of the interruption.
            expected_end_time (float): The expected end time of the state.
            state_type (StateTypeEnum): The type of the state.
        """
        self._event_time = end_time
        self._expected_end_time = expected_end_time
        self._activity = StateEnum.end_interrupt
        self._state_type = state_type

    def log_end_state(self, end_time: float, state_type: StateTypeEnum):
        """
        Logs the end of a state.

        Args:
            end_time (float): The end time of the state.
            state_type (StateTypeEnum): The type of the state.
        """
        self._event_time = end_time
        self._activity = StateEnum.end_state
        self._state_type = state_type


def debug_logging(state_instance: State, msg: str):
    """
    Logs a debug message for a state.

    Args:
        state_instance (State): The state.
        msg (str): The message.
    """
    logger.debug({"ID": state_instance.state_data.ID, "sim_time": state_instance.env.now, "resource": state_instance.resource.data.ID, "event": msg})


class State(ABC, BaseModel):
    """
    Abstract class that represents a state of a resource in the simulation. A state has a process that is simulated when the resource starts a state. States can exist in parallel and can interrupt each other.

    Args:
        state_data (StateData): The data of the state.
        time_model (time_model.TimeModel): The time model of the state.
        env (sim.Environment): The simulation environment.
        active (events.Event, optional): Event that indidcates if the state is active. Defaults to None.
        finished_process (events.Event, optional): Event that indicates if the state is finished. Defaults to None.
        resource (resources.Resource, optional): The resource the state belongs to. Defaults to None.
        process (Optional[events.Process], optional): The process of the state. Defaults to None.
        state_info (StateInfo, optional): The state information of the state. Defaults to None.
    """
    state_data: StateData
    time_model: time_model.TimeModel
    env: sim.Environment
    active: events.Event = Field(default=None, init=False)
    finished_process: events.Event = Field(default=None, init=False)
    resource: resources.Resource = Field(init=False, default=None)
    process: Optional[events.Process] = Field(default=None)
    state_info: StateInfo = Field(None)

    model_config=ConfigDict(arbitrary_types_allowed=True)


    def set_resource(self, resource_model: resources.Resource) -> None:
        """
        Sets the resource of the state.

        Args:
            resource_model (resources.Resource): The resource the state belongs to.
        """
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
        """
        Runs a single process of the state. The process is the key component for the behavior of the state while simulating. All the logic of the state is implemented in the process.

        Yields:
            Generator: The generator of the process.
        """
        pass

    @abstractmethod
    def interrupt_process(self):
        """
        Interrupts the process of the state. 
        """
        pass

    def activate_state(self):
        """
        Activates the state and at start of the simulation.
        """
        pass

    def prepare_for_run(self):
        """
        Prepares the state for running the process of a state.
        """
        pass


class ProductionState(State):
    """
    Represents a production state of a resource in the simulation. A production state has a process that simulates the production process which takes some time. The production state continues the creation process of a product. If a resource has a higher capacity than 1 for a process, multiple production states exist, that can run in parallel.

    Args:
        state_data (ProductionStateData): The data of the state.
        time_model (time_model.TimeModel): The time model of the state.
        env (sim.Environment): The simulation environment.
        active (events.Event, optional): Event that indidcates if the state is active. Defaults to None.
        finished_process (events.Event, optional): Event that indicates if the state is finished. Defaults to None.
        resource (resources.Resource, optional): The resource the state belongs to. Defaults to None.
        process (Optional[events.Process], optional): The process of the state. Defaults to None.
        state_info (StateInfo, optional): The state information of the state. Defaults to None.
        start (float, optional): The start time of the state. Defaults to 0.0.
        done_in (float, optional): The ramaining time for the state to finish. Defaults to 0.0.
        interrupted (bool, optional): Indicates if the state is interrupted. Defaults to False.
    """
    state_data: ProductionStateData
    start: float = 0.0
    done_in: float = 0.0
    interrupted: bool = False

    def prepare_for_run(self):
        self.finished_process = events.Event(self.env)

    def activate_state(self):
        self.active = events.Event(self.env).succeed()

    def process_state(self, time: Optional[float] = None) -> Generator:
        if not time:
            time = self.time_model.get_next_time()
        self.done_in = time
        while True:
            try:
                if self.interrupted:
                    debug_logging(self, f"interrupted while waiting for activation or activation of resource")
                    yield events.AllOf(self.env, [self.active, self.resource.active])
                    self.interrupted = False
                debug_logging(self, f"wait for activation or activation of resource before process")
                yield events.AllOf(self.env, [self.resource.active, self.active])
                break
            except exceptions.Interrupt:
                if not self.interrupted:
                    raise RuntimeError(f"Simpy interrupt occured at {self.state_data.ID} although process is not interrupted")
        while self.done_in:
            try:
                if self.interrupted:
                    self.state_info.log_start_interrupt_state(
                        self.env.now, StateTypeEnum.production
                    )
                    self.update_done_in()
                    debug_logging(self, f"interrupted process that ends in {self.done_in}")
                    yield events.AllOf(self.env, [self.active, self.resource.active])
                    debug_logging(self, f"interrupt over for process that ends in {self.done_in}")
                    self.interrupted = False
                    self.state_info.log_end_interrupt_state(
                        self.env.now, self.env.now + self.done_in, StateTypeEnum.production
                    )
                self.start = self.env.now
                self.state_info.log_start_state(
                        self.start, self.start + self.done_in, StateTypeEnum.production
                )
                debug_logging(self, f"starting process that ends in {self.done_in}")
                yield self.env.timeout(self.done_in)
                self.done_in = 0  # Set to 0 to exit while loop.

            except exceptions.Interrupt:
                if not self.interrupted:
                    raise RuntimeError(f"Simpy interrupt occured at {self.state_data.ID} although process is not interrupted")
        debug_logging(self, f"process finished")
        self.state_info.log_end_state(self.env.now, StateTypeEnum.production)
        #print(f"product {self.state_data} finished at {self.env.now}")
        self.finished_process.succeed()

    def update_done_in(self):
        if self.start == 0:
            return
        self.done_in -= (self.env.now - self.start)  # How much time left?
        if self.done_in < 0:
            self.done_in = 0

    def interrupt_process(self):
        if self.process and self.process.is_alive and not self.interrupted:
            self.interrupted = True
            self.process.interrupt()



class TransportState(State):
    """
    Represents a transport state of a resource in the simulation. A transport state has a process that simulates the transport of a product. The transport state continues the transport process of a product. If a resource has a higher capacity than 1 for a process, multiple transport states exist, that can run in parallel but only with the same target and end location.

    Args:
        state_data (TransportStateData): The data of the state.
        time_model (time_model.TimeModel): The time model of the state.
        env (sim.Environment): The simulation environment.
        active (events.Event, optional): Event that indidcates if the state is active. Defaults to None.
        finished_process (events.Event, optional): Event that indicates if the state is finished. Defaults to None.
        resource (resources.Resource, optional): The resource the state belongs to. Defaults to None.
        process (Optional[events.Process], optional): The process of the state. Defaults to None.
        state_info (StateInfo, optional): The state information of the state. Defaults to None.
        start (float, optional): The start time of the state. Defaults to 0.0.
        done_in (float, optional): The ramaining time for the state to finish. Defaults to 0.0.
        interrupted (bool, optional): Indicates if the state is interrupted. Defaults to False.
        loading_time_model (time_model.TimeModel, optional): The time model of the loading time. Defaults to None.
    """
    state_data: TransportStateData
    loading_time_model: Optional[time_model.TimeModel] = None
    unloading_time_model: Optional[time_model.TimeModel] = None
    start: float = 0.0
    done_in: float = 0.0
    interrupted: bool = False
    loading_time: float = 0.0
    unloading_time: float = 0.0

    def prepare_for_run(self):
        self.finished_process = events.Event(self.env)

    def activate_state(self):
        self.active = events.Event(self.env).succeed()

    def handle_loading(self, action: str) -> Generator:
        #loading_time = loading_time if loading_time is not None else self.loading_time_model.get_next_time()
        if action == "loading":
            time_model = self.loading_time_model
        elif action == "unloading":
            time_model = self.unloading_time_model
        else:
            raise ValueError(f"Unknown action {action}")
        
        time = time_model.get_next_time() if time_model else 0

        try:
            if self.interrupted:
                debug_logging(self, f"interrupted during {action}")
                yield self.env.timeout(time)
                self.interrupted = False
            debug_logging(self, f"loading completed")
        except exceptions.Interrupt:
            if not self.interrupted:
                raise RuntimeError(f"Simpy interrupt occured at {self.state_data.ID} although process is not interrupted")
        
    def process_state(self, target: List[float], initial_transport_step: bool, last_transport_step: bool) -> Generator:
        self.done_in = self.time_model.get_next_time(
            origin=self.resource.get_location(), target=target
        )
        if initial_transport_step and hasattr(self.time_model, "reaction_time") and self.time_model.time_model_data.reaction_time:
            self.done_in -= self.time_model.time_model_data.reaction_time

        while True:
            try:
                if self.interrupted:
                    debug_logging(self, f"interrupted while waiting for activation or activation of resource")
                    yield events.AllOf(self.env, [self.active, self.resource.active])
                    self.interrupted = False
                debug_logging(self, f"wait for activation or activation of resource before process")
                yield events.AllOf(self.env, [self.resource.active, self.active])
                break
            except exceptions.Interrupt:
                if not self.interrupted:
                    raise RuntimeError(f"Simpy interrupt occured at {self.state_data.ID} although process is not interrupted")
        yield self.env.process(self.handle_loading("loading"))
        while self.done_in:
            try:
                if self.interrupted:
                    self.state_info.log_start_interrupt_state(
                        self.env.now, StateTypeEnum.transport
                    )
                    self.update_done_in()
                    debug_logging(self, f"interrupted process that ends in {self.done_in}")
                    yield events.AllOf(self.env, [self.active, self.resource.active])
                    debug_logging(self, f"interrupt over for process that ends in {self.done_in}")
                    self.interrupted = False
                    self.state_info.log_end_interrupt_state(
                        self.env.now, self.env.now + self.done_in, StateTypeEnum.transport
                    )
                self.start = self.env.now
                self.state_info.log_start_state(
                self.start, self.start + self.done_in, StateTypeEnum.transport
                    )
                debug_logging(self, f"starting process that ends in {self.done_in}")
                yield self.env.timeout(self.done_in)
                self.done_in = 0  # Set to 0 to exit while loop.
            except exceptions.Interrupt:
                if not self.interrupted:
                    raise RuntimeError(f"Simpy interrupt occured at {self.state_data.ID} although process is not interrupted")
        yield from self.handle_loading("unloading")
        debug_logging(self, f"process finished")
        self.state_info.log_end_state(self.env.now, StateTypeEnum.transport)
        self.finished_process.succeed()

    def update_done_in(self):
        self.done_in -= (self.env.now - self.start)  # How much time left?
        if self.done_in < 0:
            self.done_in = 0

    def interrupt_process(self):
        if self.process and self.process.is_alive and not self.interrupted:
            self.interrupted = True
            self.process.interrupt()


class BreakDownState(State):
    """
    Represents a breakdown state of a resource in the simulation. A breakdown state has a process that simulates the breakdown of a resource. All other running production, transport or setup states get interrupted.

    Args:
        state_data (BreakDownStateData): The data of the state.
        time_model (time_model.TimeModel): The time model of the state.
        env (sim.Environment): The simulation environment.
        active (events.Event, optional): Event that indidcates if the state is active. Defaults to None.
        finished_process (events.Event, optional): Event that indicates if the state is finished. Defaults to None.
        resource (resources.Resource, optional): The resource the state belongs to. Defaults to None.
        process (Optional[events.Process], optional): The process of the state. Defaults to None.
        state_info (StateInfo, optional): The state information of the state. Defaults to None.
        repair_time_model (time_model.TimeModel, optional): The time model of the repair time. Defaults to None.
    """
    state_data: BreakDownStateData
    repair_time_model: time_model.TimeModel
    active_breakdown: bool = False

    @model_validator(mode="before")
    def post_init(cls, values):
        values["active"] = events.Event(values["env"])
        return values

    def process_state(self) -> Generator:
        while True:
            yield self.env.process(self.wait_for_breakdown())
            self.active_breakdown = True
            debug_logging(self, f"breakdown occured, start interrupting processes")
            self.resource.interrupt_states()
            repair_time = self.repair_time_model.get_next_time()
            debug_logging(self, f"interrupted states, starting breakdown for {repair_time}")
            self.state_info.log_start_state(
                self.env.now, self.env.now + repair_time, StateTypeEnum.breakdown
            )
            yield self.env.timeout(repair_time)
            self.active_breakdown = False
            self.resource.activate()
            debug_logging(self, f"breakdown finished, reactivating resource")
            self.state_info.log_end_state(self.env.now, StateTypeEnum.breakdown)

    def wait_for_breakdown(self):
        yield self.env.timeout(self.time_model.get_next_time())

    def interrupt_process(self):
        pass


class ProcessBreakDownState(State):
    """
    Represents a process breakdown state of a resource in the simulation. A process breakdown state has a process that simulates the breakdown of a process of a resource. Only production states of this type of process get interrupted. Also all setup states get interrupted.

    Args:
        state_data (ProcessBreakDownStateData): The data of the state.
        time_model (time_model.TimeModel): The time model of the state.
        env (sim.Environment): The simulation environment.
        active (events.Event, optional): Event that indidcates if the state is active. Defaults to None.
        finished_process (events.Event, optional): Event that indicates if the state is finished. Defaults to None.
        resource (resources.Resource, optional): The resource the state belongs to. Defaults to None.
        process (Optional[events.Process], optional): The process of the state. Defaults to None.
        state_info (StateInfo, optional): The state information of the state. Defaults to None.
        production_states (List[State], optional): The production states of the process. Defaults to None.
        repair_time_model (time_model.TimeModel, optional): The time model of the repair time. Defaults to None.
    """
    state_data: ProcessBreakDownStateData
    production_states: List[State] = None
    repair_time_model: time_model.TimeModel

    @model_validator(mode="before")
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
            debug_logging(self, f"breakdown occured, start interrupting processes")
            yield events.AllOf(
                self.env, [state.active for state in self.production_states]
            )
            debug_logging(self, f"interrupted states, starting breakdown for {self.repair_time_model.get_next_time()}")
            for state in self.production_states + self.resource.setup_states:
                state.deactivate()
            for state in self.production_states + self.resource.setup_states:
                if state.process and state.process.is_alive and not state.interrupted:
                    state.interrupt_process()
            repair_time = self.repair_time_model.get_next_time()
            debug_logging(self, f"interrupted states, starting breakdown for {repair_time}")
            self.state_info.log_start_state(
                self.env.now, self.env.now + repair_time, StateTypeEnum.process_breakdown
            )
            yield self.env.timeout(repair_time)
            self.state_info.log_end_state(self.env.now, StateTypeEnum.process_breakdown)
            debug_logging(self, f"breakdown finished, reactivating states")
            for state in self.production_states + self.resource.setup_states:
                state.activate()

    def wait_for_breakdown(self):
        yield self.env.timeout(self.time_model.get_next_time())

    def interrupt_process(self):
        pass


class SetupState(State):
    """
    Represents a setup state of a resource in the simulation. A setup state has a process that simulates the setup of a resource. This changes the current setup of the resource and allows it processing of other types of processes with their associated production or transport states.

    Args:
        state_data (SetupStateData): The data of the state.
        time_model (time_model.TimeModel): The time model of the state.
        env (sim.Environment): The simulation environment.
        active (events.Event, optional): Event that indidcates if the state is active. Defaults to None.
        finished_process (events.Event, optional): Event that indicates if the state is finished. Defaults to None.
        resource (resources.Resource, optional): The resource the state belongs to. Defaults to None.
        process (Optional[events.Process], optional): The process of the state. Defaults to None.
        state_info (StateInfo, optional): The state information of the state. Defaults to None.
        start (float, optional): The start time of the state. Defaults to 0.0.
        done_in (float, optional): The time the state is done in. Defaults to 0.0.

    Attributes:
        interrupt_processed (events.Event): Event that indicates if the state is interrupted. Defaults to None.
    """
    state_data: SetupStateData
    start: float = 0.0
    done_in: float = 0.0
    interrupted: bool = False

    def prepare_for_run(self):
        self.finished_process = events.Event(self.env)

    def activate_state(self):
        self.active = events.Event(self.env).succeed()

    def process_state(self) -> Generator:
        self.done_in = self.time_model.get_next_time()
        while True:
            try:
                if self.interrupted:
                    debug_logging(self, f"interrupted while waiting for activation or activation of resource")
                    yield events.AllOf(self.env, [self.active, self.resource.active])
                    self.interrupted = False
                debug_logging(self, f"wait for activation or activation of resource before process")
                yield events.AllOf(self.env, [self.resource.active, self.active])
                running_processes = [
                    state.process
                    for state in self.resource.production_states
                    if (state.process and state.process.is_alive)
                ]
                debug_logging(self, f"waiting for running processes to finish")
                yield events.AllOf(self.env, running_processes)
                break
            except exceptions.Interrupt:
                if not self.interrupted:
                    raise RuntimeError(f"Simpy interrupt occured at {self.state_data.ID} although process is not interrupted")
        while self.done_in:
            try:
                if self.interrupted:
                    self.state_info.log_start_interrupt_state(
                        self.env.now, StateTypeEnum.setup
                    )
                    self.update_done_in()
                    debug_logging(self, f"interrupted process that ends in {self.done_in}")
                    yield events.AllOf(self.env, [self.active, self.resource.active])
                    self.interrupted = False
                    debug_logging(self, f"interrupt over for process that ends in {self.done_in}")
                    self.state_info.log_end_interrupt_state(
                        self.env.now, self.env.now + self.done_in, StateTypeEnum.setup
                    )
                self.start = self.env.now
                self.state_info.log_start_state(
                        self.start, self.start + self.done_in, StateTypeEnum.setup
                )
                debug_logging(self, f"starting process that ends in {self.done_in}")
                yield self.env.timeout(self.done_in)
                self.done_in = 0
            except exceptions.Interrupt:
                if not self.interrupted:
                    raise RuntimeError(f"Simpy interrupt occured at {self.state_data.ID} although process is not interrupted")
        debug_logging(self, f"process finished")
        self.state_info.log_end_state(self.env.now, StateTypeEnum.setup)
        self.finished_process.succeed()

    def update_done_in(self):
        self.done_in -= (self.env.now - self.start)  # How much time left?
        if self.done_in < 0:
            self.done_in = 0

    def interrupt_process(self) -> Generator:
        if self.process and self.process.is_alive and not self.interrupted:
            self.interrupted = True
            self.process.interrupt()


STATE_UNION = Union[
    BreakDownState, ProductionState, TransportState, SetupState, ProcessBreakDownState
]
"""
Union Type of all states.
"""

from prodsys.simulation import resources

if TYPE_CHECKING:
    from prodsys.simulation import product