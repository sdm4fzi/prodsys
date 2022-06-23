from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Type

import simpy
import env
import resource
from time_model import TimeModel
from base import IDEntity
from util import get_class_from_str
from time_model import TimeModelFactory


@dataclass
class State(ABC, IDEntity):
    env: env.Environment
    time_model: TimeModel
    active: simpy.Event = field(default=None, init=False)
    _resource: resource.Resource = field(default=None, init=False)
    process: simpy.Process = field(default=None, init=False)

    @property
    def resource(self) -> resource.Resource:
        return self._resource

    @resource.setter
    def resource(self, resource_model: resource.Resource) -> None:
        self._resource = resource_model

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

    def process_state(self):
        """Runs a single process of a resource.
        While making a part, the machine may break multiple times.
        Request a repairman when this happens.
        """
        self.done_in = self.time_model.get_next_time()
        yield self.resource.active
        while self.done_in:
            try:
                self.start = self.env.now
                yield self.env.timeout(self.done_in)
                self.done_in = 0  # Set to 0 to exit while loop.

            except simpy.Interrupt:
                self.update_done_in()
                self.interrupt_processed = simpy.Event(self.env)
                yield self.env.process(self.interrupt())
                self.interrupt_processed.succeed()
        # TODO: parts made has to be moved to product or logger class
        self.resource.parts_made += 1

    def update_done_in(self):
        self.done_in -= self.env.now - self.start  # How much time left?
        if self.done_in < 0:
            self.done_in = 0

    def interrupt(self):
        yield self.active

    def interrupt_process(self):
        yield self.interrupt_processed
        self.interrupt_processed = simpy.Event(self.env)
        if self.process.is_alive:
            self.process.interrupt()

    def activate(self):
        try:
            self.active.succeed()
        except:
            raise RuntimeError("state is allready succeded!!")
        self.active = simpy.Event(self.env)


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

    def process_state(self, target: List[float]):
        """Runs a single process of a resource.
        While making a part, the machine may break multiple times.
        Request a repairman when this happens.
        """
        self.done_in = self.time_model.get_next_time(origin=self.resource.get_location(), target=target)
        yield self.resource.active
        while self.done_in:
            try:
                self.start = self.env.now
                yield self.env.timeout(self.done_in)
                self.done_in = 0  # Set to 0 to exit while loop.

            except simpy.Interrupt:
                self.update_done_in()
                self.interrupt_processed = simpy.Event(self.env)
                yield self.env.process(self.interrupt())
                self.interrupt_processed.succeed()
        # TODO: parts made has to be moved to product or logger class
        self.resource.location = target
        self.resource.parts_made += 1

    def update_done_in(self):
        self.done_in -= self.env.now - self.start  # How much time left?
        if self.done_in < 0:
            self.done_in = 0

    def interrupt(self):
        yield self.active

    def interrupt_process(self):
        yield self.interrupt_processed
        self.interrupt_processed = simpy.Event(self.env)
        if self.process.is_alive:
            self.process.interrupt()

    def activate(self):
        try:
            self.active.succeed()
        except:
            raise RuntimeError("state is allready succeded!!")
        self.active = simpy.Event(self.env)


class BreakDownState(State):

    def __post_init__(self):
        self.active = simpy.Event(self.env)

    def process_state(self):
        while True:
            yield self.env.process(self.wait_for_breakdown())
            self.resource.interrupt_state()
            yield self.resource.active
            self.resource.active = simpy.Event(self.env)
            # TODO: Schedule here the maintainer! or a time model for a repair
            yield self.env.timeout(3)
            self.resource.activate()

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
    'ProductionStates': ProductionState,
    'TransportState': TransportState,
    'BreakDownStates': BreakDownState,
}


@dataclass
class StateFactory:
    data: dict
    env: env.Environment
    time_model_factory: TimeModelFactory

    states: List[State] = field(default_factory=list)

    def create_states(self):
        states = self.data['states']
        for cls_name, items in states.items():
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

