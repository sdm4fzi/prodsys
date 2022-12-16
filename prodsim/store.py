from __future__ import annotations


from typing import Union
from simpy.resources import store

from prodsim.data_structures import queue_data

from prodsim import sim


class Queue(store.FilterStore):
    def __init__(self, env: sim.Environment, queue_data: queue_data.QueueData):
        self.env: sim.Environment = env
        self.queue_data: queue_data.QueueData = queue_data
        super().__init__(env, self.queue_data.capacity)



