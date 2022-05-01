
import random

import simpy


RANDOM_SEED = 42
PT_MEAN = 10.0         # Avg. processing time in minutes
PT_SIGMA = 2.0         # Sigma of processing time
MTTF = 300.0           # Mean time to failure in minutes
BREAK_MEAN = 1 / MTTF  # Param. for expovariate distribution
REPAIR_TIME = 30.0     # Time it takes to repair a machine in minutes
JOB_DURATION = 30.0    # Duration of other jobs in minutes
NUM_MACHINES = 10      # Number of machines in the machine shop
WEEKS = 4              # Simulation time in weeks
SIM_TIME = WEEKS * 7 * 24 * 60  # Simulation time in minutes


def time_per_part():
    """Return actual processing time for a concrete part."""
    return random.normalvariate(PT_MEAN, PT_SIGMA)


def time_to_failure():
    """Return time until next failure for a machine."""
    return random.expovariate(BREAK_MEAN)


from base import State, Process
from base import ValueCreatorAsset

class ProductionState(State):
    def __init__(self, asset: ValueCreatorAsset) -> None:
        self.asset: ValueCreatorAsset = asset
        self.env: env = self.asset.get_env()
        self.active = simpy.Event(self.env)
        self.done_in : float = 0.0
        self.start : float = 0.0
        self.process = self.env.process(self.process())


    def process(self):
        """Produce parts as long as the simulation runs.

               While making a part, the machine may break multiple times.
               Request a repairman when this happens.

               """
        while True:
            # Start making a new part
            self.done_in = time_per_part()
            while self.done_in:
                try:
                    # Working on the part
                    self.start = self.env.now
                    yield self.env.timeout(self.done_in)
                    self.done_in = 0  # Set to 0 to exit while loop.

                except simpy.Interrupt:
                    yield self.env.process(self.interrupt())

            # Part is done.
            self.asset.parts_made += 1

    def interrupt(self):
        self.done_in -= self.env.now - self.start  # How much time left?
        yield self.active
        self.active = simpy.Event(self.env)

class BreakDownState(State):
    def __init__(self, asset: ValueCreatorAsset) -> None:
        self.asset: ValueCreatorAsset = asset
        self.env: env = self.asset.get_env()
        self.active : simpy.Event = simpy.Event(self.env)

        self.process = self.env.process(self.process())
        self.env.process(self.interrupt())


    def process(self):
        while True:
            yield self.active
            self.active = simpy.Event(self.env)
            # Request a repairman. This will preempt its "other_job".
            with self.asset.repairman.request(priority=1) as req:
                yield req
                yield self.env.timeout(REPAIR_TIME)
            self.asset.reactivate()

    def interrupt(self):
        """Break the machine every now and then."""
        while True:
            yield self.env.timeout(time_to_failure())
            if self.asset.state is not self:
                self.asset.interrupt_active_process()
                self.asset.set_activate_state(self)


class Machine(ValueCreatorAsset):
    def start_process(self, process: Process) -> None:
        pass

    def __init__(self, env, name, repairman):
        self.env = env
        self.name = name
        self.parts_made = 0
        self.broken = False
        self.repairman = repairman

        self._state = None

        self.states = self.start_states()
        self.parts_made : int = 0

    def start_states(self):
        states = [ProductionState(self), BreakDownState(self)]
        self._state = states[0]
        print(self.state)
        return states

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, state):
        self._state = state

    def transform(self, material) -> None:
        pass

    def interrupt_active_process(self) -> None:
        self.state.process.interrupt()

    def get_env(self):
        return self.env

    def get_activate_state(self):
        return self.state

    def set_activate_state(self, state: State):
        self._state = state
        self._state.active.succeed()

    def reactivate(self):
        self.set_activate_state(self.states[0])


class Machine_old(object):
    """A machine produces parts and my get broken every now and then.

    If it breaks, it requests a *repairman* and continues the production
    after the it is repaired.

    A machine has a *name* and a numberof *parts_made* thus far.

    """
    def __init__(self, env, name, repairman):
        self.env = env
        self.name = name
        self.parts_made = 0
        self.broken = False

        # Start "working" and "break_machine" processes for this machine.
        self.process = env.process(self.working(repairman))
        env.process(self.break_machine())

    def working(self, repairman):
        """Produce parts as long as the simulation runs.

        While making a part, the machine may break multiple times.
        Request a repairman when this happens.

        """
        while True:
            # Start making a new part
            done_in = time_per_part()
            while done_in:
                try:
                    # Working on the part
                    start = self.env.now
                    yield self.env.timeout(done_in)
                    done_in = 0  # Set to 0 to exit while loop.

                except simpy.Interrupt:
                    print(2)
                    self.broken = True
                    done_in -= self.env.now - start  # How much time left?

                    # Request a repairman. This will preempt its "other_job".
                    with repairman.request(priority=1) as req:
                        yield req
                        yield self.env.timeout(REPAIR_TIME)

                    self.broken = False

            # Part is done.
            self.parts_made += 1

    def break_machine(self):
        """Break the machine every now and then."""
        while True:
            yield self.env.timeout(time_to_failure())
            if not self.broken:
                # Only break the machine if it is currently working.
                print(1)
                self.process.interrupt()
                print(3)


def other_jobs(env, repairman):
    """The repairman's other (unimportant) job."""
    while True:
        # Start a new job
        done_in = JOB_DURATION
        while done_in:
            # Retry the job until it is done.
            # It's priority is lower than that of machine repairs.
            with repairman.request(priority=2) as req:
                yield req
                try:
                    start = env.now
                    yield env.timeout(done_in)
                    done_in = 0
                except simpy.Interrupt:
                    done_in -= env.now - start


# Setup and start the simulation
print('Machine shop')
random.seed(RANDOM_SEED)  # This helps reproducing the results

# Create an environment and start the setup process
env = simpy.Environment()
repairman = simpy.PreemptiveResource(env, capacity=1)
machines = [Machine_old(env, 'Machine %d' % i, repairman)
            for i in range(NUM_MACHINES)]
env.process(other_jobs(env, repairman))


# Execute!
env.run(until=SIM_TIME)

# Analyis/results
print('Machine shop results after %s weeks' % WEEKS)
for machine in machines:
    print('%s made %d parts.' % (machine.name, machine.parts_made))
