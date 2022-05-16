from __future__ import annotations
import simpy
from dataclasses import dataclass, field
from typing import List
from collections.abc import Callable
from abc import ABC

@dataclass
class Resource(simpy.Resource):
    env: simpy.Environment
    states: List[State] = field(default_factory=list, init=False)
    production_states: List[State] = field(default_factory=list, init=False)
    active: simpy.Event = field(default=None, init=False)
    controller: Controller = field(default=None, init=False)

    def __post_init__(self):
        super(Resource, self).__init__(self.env)
        self.active = simpy.Event(self.env).succeed()

    def add_states(self, states: List[State]):
        for state in states:
            self.states.append(state)
            state.resource = self

    def add_production_states(self, states: List[State]):
        for state in states:
            self.production_states.append(state)
            state.resource = self

    def start_states(self):
        for state in self.states:
            state.process = self.env.process(state.process_state())

    def interrupt_states(self):
        for state in self.production_states:
            if state.process:
                self.env.process(state.interrupt_process())

    def run_process(self, process: str):
        for state in self.production_states:
            if state.name == process:
                state.process = self.env.process(state.process_state())
                return state.process

    def get_process(self, process: str):
        for state in self.production_states:
            if state.name == process:
                return state

    def request_process(self, process: str, material: Material):
        print("Resource asks controller")
        self.env.process(self.controller.request(process, material, self))

    def activate(self):
        print("resource succeeds active", self.env.now)
        self.active.succeed()
        print("resource has succeeded active", self.env.now)
        for state in self.states:
            state.activate()

    def get_process_time_next_process(self, process):
        for state in self.states:
            if state.name == process:
                return state.process_time

def FIFO_control_policy(current: List[Material]) -> List[Material]:
    return current.copy()


def LIFO_control_policy(current: List[Material]) -> List[Material]:
    return list(reversed(current))


@dataclass()
class Controller(ABC):
    control_policy: Callable[List[Material], List[Material]]

    def request(self, process: str, material: Material, resource: Resource):
        pass


class SimpleController(Controller):
    control_policy: Callable[List[Material], List[Material]]

    def request(self, process: str, material: Material, resource: Resource):
        with resource.request() as req:
            self.sort_queue(resource)
            print("Controller requests resource")
            yield req
            print("Controller receicves resource and starts process")
            yield resource.run_process(material.next_process)
            state_process = resource.get_process(process)
            print("delete process")
            del state_process.process
            print("Controller finished process")
            material.finished_process.succeed()

    def sort_queue(self, resource: Resource):
        pass

    def check_resource_available(self):
        pass


@dataclass
class State:
    name: str
    env: simpy.Environment
    process_time: int
    interrupt_processed: simpy.Event = field(default=None, init=False)
    active: simpy.Event = field(default=None, init=False)
    resource: Resource = field(default=None, init=False)
    process: simpy.Process = field(default=None, init=False)

    def __post_init__(self):
        self.interrupt_processed = simpy.Event(self.env).succeed()
        print(self.name, "the interrupt is initialized", self.interrupt_processed.triggered)
        self.active = simpy.Event(self.env)

    def process_state(self):
        done_in = self.process_time
        yield self.resource.active
        while done_in:
            try:
                start = self.env.now
                print(self.name, self.env.now, "start process", done_in, self.env.now)
                yield self.env.timeout(done_in)
                print("process done")
                done_in = 0

            except simpy.Interrupt:
                print(self.name, self.env.now, "Interrupt Exception", self.env.now, start)
                done_in -= self.env.now - start

                if done_in < 0:
                    done_in = 0
                self.interrupt_processed = simpy.Event(self.env)
                print("wait for interrupt end")
                yield self.env.process(self.interrupt())
                print(self.name, self.env.now, "end interrupt")
                self.interrupt_processed.succeed()
                print("continue process after interrupt, missing: ", done_in)
        print("finished_process")

    def interrupt_process(self):
        print(self.name, "the interrupt is waiting", self.interrupt_processed.triggered)
        yield self.interrupt_processed
        print(self.name, "the interrupt has waited ", self.interrupt_processed.triggered)
        self.interrupt_processed = simpy.Event(self.env)
        print(self.name, "the interrupt ist happening", self.interrupt_processed.triggered)
        if self.process.is_alive:
            print(self.name, "interrupt running process")
            self.process.interrupt()
        else:
            print(self.name, "is not interrupted as not alive")

    def interrupt(self):
        print(self.name, "wait for interrupt end", self.env.now)
        yield self.resource.active

    def activate(self):
        try:
            self.active.succeed()
        except:
            raise RuntimeError("state is allready succeded!!")
        self.active = simpy.Event(self.env)


@dataclass
class BreakdownState(State):
    repair_time: int

    def process_state(self):
        while True:
            yield self.env.timeout(self.process_time)
            print(self.name, "Breakdown happens at", self.env.now)
            self.resource.interrupt_states()
            print(self.name, "wait for repair at", self.env.now)
            yield self.resource.active
            self.resource.active = simpy.Event(self.env)
            print(self.name, "Start repair at", self.env.now)
            self.resource.active = simpy.Event(self.env)
            yield self.env.timeout(3)
            print(self.name, "End repair.", self.env.now)
            self.resource.activate()

    def interrupt_process(self):
        pass

@dataclass
class Material:
    env: simpy.Environment
    processes: List[str]
    process: simpy.Process = field(default=None, init=False)
    next_process: str = field(default=None, init=False)
    next_resource: Resource = field(default=None, init=False)
    finished_process: simpy.Event = field(default=None, init=False)

    def __post_init__(self):
        self.finished_process = simpy.Event(self.env)
        self.set_next_process()

    def process_material(self):
        while self.next_process:
            print("Material requests process", self.next_process)
            self.next_resource.request_process(self.next_process, self)
            print("Material waits for process to finish process", self.next_process)
            yield self.finished_process
            print("Material finished process", self.next_process)
            self.finished_process = simpy.Event(self.env)

            self.set_next_process()
            print("__________get next process", self.next_process)
        print("finished material at", self.env.now)


    def set_next_process(self):
        if not self.processes:
            self.next_process = None
            print("material is finsihed at", self.env.now)
        else:
            self.next_process = self.processes.pop()



def generate_material(env: simpy.Environment, arrival_time: int, resource: Resource):
    while True:
        yield env.timeout(arrival_time)
        print("create material")
        m = Material(env, ['p1', 'p2', 'p2'])
        m.next_resource = resource
        m.process = env.process(m.process_material())


env = simpy.Environment()
p1 = State('p1', env, process_time=10)
p2 = State('p2', env, process_time=13)
s1 = BreakdownState('s1', env, process_time=8, repair_time=1)
s2 = BreakdownState('s2', env, process_time=9, repair_time=2)

r = Resource(env)
r.add_states([s1, s2])
r.add_production_states([p1, p2])
r.start_states()

c = SimpleController(FIFO_control_policy)
r.controller = c

env.process(generate_material(env, 19, r))


env.run(500)
