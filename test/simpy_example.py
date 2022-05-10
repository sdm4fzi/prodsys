
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


from test.base import State
from test.base import ValueCreatorAsset
from test.base import Job

class ConcreteJob(Job):
    def __init__(self, material, process_sequence):
        self.material = material
        self.process_sequence = process_sequence

    def request_processing(self):
        pass

    def request_transport(self):
        pass

    def get_next_process(self):
        pass

    def get_material_for_process(self):
        pass

class ProductionState(State):
    def __init__(self, asset: ValueCreatorAsset) -> None:
        self.asset: ValueCreatorAsset = asset
        self.env: env_object = self.asset.get_env()
        self.active: simpy.Event = simpy.Event(self.env)
        self.done_in : float = 0.0
        self.start : float = 0.0
        self.process  = self.env.process_state(self.process())


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
                    yield self.env.process_state(self.interrupt())

            # Part is done.
            # TODO: parts made has to be moved to product or logger class
            self.asset.parts_made += 1

    def interrupt(self):
        self.done_in -= self.env.now - self.start  # How much time left?
        yield self.active

    def activate(self):
        self.active.succeed()
        self.active = simpy.Event(self.env)

class BreakDownState(State):
    def __init__(self, asset: ValueCreatorAsset) -> None:
        self.asset: ValueCreatorAsset = asset
        self.env: env_object = self.asset.get_env()
        self.active : simpy.Event = simpy.Event(self.env)

        self.process = self.env.process_state(self.process())
        self.env.process_state(self.interrupt())


    def process(self):
        while True:
            yield self.active
            # Request a repairman. This will preempt its "other_job".
            # TODO: this request has to be made in a controller
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

    def activate(self):
        self.active.succeed()
        self.active = simpy.Event(self.env)

class Machine(ValueCreatorAsset, simpy.PreemptiveResource):
    def __init__(self, env, name, repairman, capacity=1):
        super().__init__(env, capacity)
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
        self.state.process_state.interrupt()

    def get_env(self):
        return self.env

    def get_activate_state(self):
        return self.state

    def set_activate_state(self, state: State):
        self.state = state
        self.state.activate()

    def reactivate(self):
        for state in self.states:
            if type(state) is ProductionState:
                self.set_activate_state(state)


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

if __name__ == '__main__':
    # Setup and start the simulation
    print('Machine shop')
    random.seed(RANDOM_SEED)  # This helps reproducing the results

    import time

    start = time.time()

    for _ in range(1):
        # Create an environment and start the setup process
        env_object = simpy.Environment()
        repairman_object = simpy.PreemptiveResource(env_object, capacity=1)
        machine_objects = [Machine(env_object, 'Machine %d' % i, repairman_object)
                           for i in range(NUM_MACHINES)]
        env_object.process(other_jobs(env_object, repairman_object))


        # Execute!
        env_object.run(until=SIM_TIME)

    # Analysis/results
    print('Machine shop results after %s weeks' % WEEKS)
    for machine in machine_objects:
        print('%s made %d parts.' % (machine.name, machine.parts_made))

    print(f"Took: {time.time() - start} seconds")