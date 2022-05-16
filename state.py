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

class ProductionState(State):
    interrupt_processed: simpy.Event

    def __post_init__(self):
        self.active = simpy.Event(self.env).succeed()
        self.start = 0.0
        self.done_in = 0.0
        self.interrupt_processed = simpy.Event(self.env).succeed()

    def process_state(self):
        """Produce parts as long as the simulation runs.

               While making a part, the machine may break multiple times.
               Request a repairman when this happens.

               """
        while True:
            # Start making a new part
            # TODO: add here this logical request, which is created and updated by the controller class
            # yield self.resource.req
            self.done_in = self.time_model.get_next_time()
            print(self.resource.description, self.description, self.done_in)
            while self.done_in:
                try:
                    # Working on the part
                    self.start = self.env.now
                    yield self.env.timeout(self.done_in)
                    self.done_in = 0  # Set to 0 to exit while loop.

                except simpy.Interrupt:
                    print("Exception")
                    self.interrupt_processed = simpy.Event(self.env)
                    yield self.env.process(self.interrupt())
                    self.interrupt_processed.succeed()

            # Part is done.
            # TODO: parts made has to be moved to product or logger class
            self.resource.parts_made += 1
            print(self.resource.description, self.resource.parts_made, self.env.now)

    def interrupt(self):
        print(self.description, "here", self.env.now)
        self.done_in -= self.env.now - self.start  # How much time left?
        print(self.description, "wait for actication", self.env.now)
        yield self.active
        print(self.description, "activated", self.env.now)

    def interrupt_process(self):
        print(self.description, "wait for interruptable process", self.interrupt_processed.triggered)
        yield self.interrupt_processed
        print(self.description, "interrupt process")
        self.process.interrupt()


class BreakDownState(State):

    def __post_init__(self):
        self.active = simpy.Event(self.env)
        # self.process = self.env.process(self.process_state())

    def process_state(self):
        while True:
            print(self.resource.description, self.description)
            yield self.env.process(self.wait_for_schedule())
            # Request a repairman. This will preempt its "other_job".
            # TODO: this request has to be made in a controller
            # with self.resource.request_repair() as req:
            #     yield req
            print("repair!")
            yield self.env.timeout(10)
            self.resource.reactivate()

    def wait_for_schedule(self):
        print(self.resource.description, self.description, "wait for schedule")
        yield self.env.timeout(self.time_model.get_next_time())
        print(self.resource.description, self.description, "interrupt")
        # TODO: add that only the states, that are interruptable are interrupted
        self.resource.interrupt_state()
        yield self.active

    def interrupt_process(self):
        yield self.env.timeout(1)


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

    def get_states(self, IDs: List[str]) -> List[State]:
        return [st for st in self.states if st.ID in IDs]

