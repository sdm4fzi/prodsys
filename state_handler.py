from abc import ABC, abstractmethod
import re
from state import State
from typing import List
from resource import Resource

from __future__ import annotations

from abc import ABC, abstractmethod
from resource import Resource
from dataclasses import Field, dataclass
from uuid import UUID, uuid1
from typing import List, Tuple, Optional
import simpy
from process import Process
from material import Material
from time_model import TimeModel
from collections.abc import Callable


class StateHandler(ABC):
    env : simpy.Environment
    states : List[State]
    resource : Resource

    def set_resource(self, resource: Resource):
        self.resource = resource

    def set_state(self, state: State):
        self.states.append(state)
        

    @abstractmethod
    def process_state(self, state: State):
        if state in self.states and self.resource is not None:
            self.env.process(state.process_state(self.resource))

    @abstractmethod
    def change_state(self, state: State) -> None:
        pass

    def add_state(self, state: State) -> None:
        self.states.append(state)

    @abstractmethod
    def process_state(self, state: State) -> None:
        pass

    @abstractmethod
    def reactivate(self):
        pass

    @abstractmethod
    def interrupt_state(self):
        pass

    def get_active_states(self) -> List[State]:
        return self.states

    @abstractmethod
    def set_active_state(self, state: State):
        self.state = state


@dataclass
class State(ABC):
    env : simpy.Environment
    time_model : TimeModel
    active : simpy.Event
    start : float
    done_in : float

    @abstractmethod
    def __post_init__(self):
        pass

    @abstractmethod
    def process_state(self):
        pass

    def activate(self):
        self.active.succeed()
        self.active = simpy.Event(self.env)


class InterruptState(State):

    @abstractmethod
    def __post_init__(self):
        pass

    @abstractmethod
    def interrupt(self):
        pass


class ProductionState(InterruptState):

    def __post_init__(self):
        self.start = 0.0
        self.done_in = 0.0


    def process_state(self, resource: Resource):
        """Produce parts as long as the simulation runs.

               While making a part, the machine may break multiple times.
               Request a repairman when this happens.

               """
        while True:
            yield resource.requested

            # Start making a new part
            self.done_in = self.time_model.get_next_time()
            while self.done_in:
                try:
                    # Working on the part
                    self.start = self.env.now
                    yield self.env.timeout(self.done_in)
                    self.done_in = 0  # Set to 0 to exit while loop.

                except simpy.Interrupt:
                    yield self.env.process(self.interrupt())

            # Part is done.
            # TODO: parts made has to be moved to product or logger class
            resource.add_produced_part()

    def interrupt(self):
        self.done_in -= self.env.now - self.start  # How much time left?
        yield self.active

class BreakDownState(State):

    def process_state(self, env : simpy.Environment, resource:Resource):
        while True:
            yield env.process(self.wait_for_schedule())
            # Request a repairman. This will preempt its "other_job".
            # TODO: this request has to be made in a controller
            with resource.request_repair() as req:
                yield req
            self.resource.reactivate()

    def wait_for_schedule(self):
        yield self.env.timeout(self.time_model.get_next_time())
        if self.resource.state is not self:
            self.resource.interrupt_state()
            self.resource.set_active_state(self)
        yield self.active



