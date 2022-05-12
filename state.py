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

@dataclass
class State(ABC):
    env : simpy.Environment
    time_model : TimeModel
    active : simpy.Event
    start : float
    done_in : float
    resource : Resource


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
        self.process : simpy.Process = self.env.process(self.process_state())


    def process_state(self):
        """Produce parts as long as the simulation runs.

               While making a part, the machine may break multiple times.
               Request a repairman when this happens.

               """
        while True:
            # Start making a new part
            # TODO: add here this logical request, which is created and updated by the controller class
            yield req
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
        if self.resource.state is not self:
            self.resource.interrupt_state()
            self.resource.set_active_state(self)
        yield self.active



