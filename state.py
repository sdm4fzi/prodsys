from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Type

import simpy
from env import Environment
import resource
from time_model import TimeModel
from base import IDEntity
from util import get_class_from_str
from time_model import TimeModelFactory


@dataclass
class State(ABC, IDEntity):
    env: Environment
    time_model: TimeModel
    active: simpy.Event = field(default=None, init=False)
    _resource: resource.Resource = field(default=None, init=False)

    @property
    def resource(self) -> resource.Resource:
        return self._resource

    @resource.setter
    def resource(self, resource_model: resource.Resource) -> None:
        self._resource = resource_model

    def activate(self):
        self.active.succeed()
        self.active = simpy.Event(self.env)

    @abstractmethod
    def __post_init__(self):
        pass

    @abstractmethod
    def process_state(self):
        pass


class InterruptState(State):

    @abstractmethod
    def __post_init__(self):
        pass

    @abstractmethod
    def interrupt(self):
        pass


class ProductionState(InterruptState):
    def __post_init__(self):
        self.active = simpy.Event(self.env)
        self.start = 0.0
        self.done_in = 0.0
        self.process: simpy.Process = self.env.process(self.process_state())

    def process_state(self):
        """Produce parts as long as the simulation runs.

               While making a part, the machine may break multiple times.
               Request a repairman when this happens.

               """
        while True:
            # Start making a new part
            # TODO: add here this logical request, which is created and updated by the controller class
            yield self._resource.req
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
            self.resource.parts_made += 1

    def interrupt(self):
        self.done_in -= self.env.now - self.start  # How much time left?
        yield self.active


class BreakDownState(State):

    def __post_init__(self):
        self.active = simpy.Event(self.env)
        self.process = self.env.process(self.process_state())

    def process_state(self):
        while True:
            yield self.env.process(self.wait_for_schedule())
            # Request a repairman. This will preempt its "other_job".
            # TODO: this request has to be made in a controller
            with self.resource.request_repair() as req:
                yield req
            self.resource.reactivate()

    def wait_for_schedule(self):
        yield self.env.timeout(self.time_model.get_next_time())
        # TODO: add that only the states, that are interruptable are interrupted
        self.resource.interrupt_state()
        yield self.active


STATE_DICT: dict = {
    'ProductionStates': ProductionState,
    'BreakDownStates': BreakDownState,
}


@dataclass
class StateFactory:
    data: dict
    env: Environment
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

    def get_time_model(self, ID):
        return [st for st in self.states if st.ID == ID]
