from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

import simpy

import base
from material import Material
from process import Process
from state import State


@dataclass
class Resource(ABC, simpy.Resource, base.IDEntity):
    processes: List[Process]
    parts_made: int = field(default=0, init=False)
    available: simpy.Event
    states: List[State] = field(default_factory=list, init=False)

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


@dataclass
class MaterialRegistry(ABC):
    a: int


@dataclass
class Router(ABC):

    @abstractmethod
    def determine_next_processes(self, material: Material) -> List[Process]:
        pass

    @abstractmethod
    def get_next_possible_resources(self, process: Process):
        pass
