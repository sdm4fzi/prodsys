from __future__ import annotations

import contextlib
import random
import time
from typing import Any, TYPE_CHECKING

import numpy as np
from simpy import core
from simpy import events


from prodsys.util import util

if util.run_from_ipython():
    from tqdm.notebook import tqdm
else:
    from tqdm import tqdm

# from .factories import state_factory, time_model_factory

if TYPE_CHECKING:
    from prodsys.simulation import request


VERBOSE = 1
"""
Determines whether the simulation should be verbose or not. If set to 1, a progress bar will be shown. Otherwise, no progress bar will be shown.
"""


@contextlib.contextmanager
def temp_seed(seed: int):
    """
    Context manager for temporarily setting the seed of the random number generators. Is necessary when optimizing with another random seed but still wanting to use the same seed for the simulation.

    Args:
        seed (int): The seed to set for the simulation run.
    """
    np_state = np.random.get_state()
    p_state = random.getstate()
    np.random.seed(seed)
    random.seed(seed)
    try:
        yield
    finally:
        np.random.set_state(np_state)
        random.setstate(p_state)


class Environment(core.Environment):
    """
    Class to represent the simulation environment. It is a subclass of simpy.Environment and adds a progress bar to the simulation.

    Args:
        seed (int, optional): The seed to set for the simulation run. Defaults to 0.

    Attributes:
        seed (int): The seed to set for the simulation run.
        pbar (Any): The progress bar.
        last_update (int): The last time the progress bar was updated.
    """

    def __init__(self, seed: int = 0) -> None:
        super().__init__()
        self.seed: int = seed
        self.pbar: Any = None
        self.last_update = 0
        self.last_update_time = 0

    def run(self, time_range: float):
        """
        Runs the simulation for a given time range.

        Args:
            time_range (int): The time range to run the simulation for in minutes.
        """
        with temp_seed(self.seed):
            if VERBOSE == 1:
                self.pbar = tqdm(total=time_range)

            super().run(time_range)
            if VERBOSE == 1:
                self.pbar.update(time_range - self.last_update)
                self.pbar.close()

    def run_until(self, until: events.Event):
        """
        Runs the simulation until a given event.

        Args:
            until (events.Event): The event to run the simulation until.
        """
        super().run(until=until)

    def update_progress_bar(self):
        """
        Updates the progress bar.

        Args:
            time (float): The time to update the progress bar to.
        """
        if VERBOSE == 1:
            now = round(self.now)
            if now > self.last_update and time.perf_counter() - self.last_update_time > 0.1:
                self.last_update_time = time.perf_counter()
                self.pbar.update(now - self.last_update)
                self.last_update = now
