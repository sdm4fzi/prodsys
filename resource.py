from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

import simpy
import env
import base
from process import Process
import state


@dataclass
class Resource(ABC, simpy.Resource, base.IDEntity):
    env: env.Environment
    processes: List[Process]
    parts_made: int = field(default=0, init=False)
    req: simpy.Event = field(default=None, init=False)
    available: simpy.Event = field(default=None, init=False)
    states: List[state.State] = field(default_factory=list, init=False)

    def __post_init__(self):
        self.req = simpy.Event(self.env)
        self.available = simpy.Event(self.env)

    @abstractmethod
    def change_state(self, input_state: state.State) -> None:
        pass

    def add_state(self, input_state: state.State) -> None:
        self.states.append(input_state)

    @abstractmethod
    def process_state(self, input_state: state.State) -> None:
        pass

    @abstractmethod
    def reactivate(self, input_state: state.State):
        pass

    @abstractmethod
    def interrupt_state(self, input_state: state.State):
        pass

    def get_active_states(self) -> List[state.State]:
        return self.states

    def request_repair(self):
        pass


class ConcreteResource(Resource):

    def __post_init__(self):
        self.req = simpy.Event(self.env)
        self.available = simpy.Event(self.env)

    def change_state(self, input_state: state.State) -> None:
        pass

    def add_state(self, input_state: state.State) -> None:
        self.states.append(input_state)
        input_state.resource = self

    def process_state(self, input_state: state.State) -> None:
        self.env.process(input_state.process_state())

    def reactivate(self, input_state: state.State):
        input_state.activate()

    def interrupt_state(self, input_state: state.InterruptState):
        input_state.interrupt()

    def get_active_states(self) -> List[state.State]:
        pass

    def request_repair(self):
        pass
