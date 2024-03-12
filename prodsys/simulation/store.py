from __future__ import annotations
from typing import List
from pydantic import BaseModel


from simpy.resources import store

import logging
logger = logging.getLogger(__name__)

from prodsys.models import queue_data

from prodsys.simulation import sim


class Queue(store.FilterStore):
    """
    Class for storing products in a queue. The queue is a filter store with a limited or unlimited capacity, where product can be put and get from. 

    Args:
        env (simpy.Environment): The simulation environment.
        queue_data (queue_data.QueueData): The queue data object.

    Attributes:
        capacity (int, optional): The capacity of the queue. If 0 in the queue_data, the capacity is set to infinity.
        _pending_put (int): The number of products that are reserved for being put into the queue. Avoids bottleneck in the simulation.

    """
    def __init__(self, env: sim.Environment, queue_data: queue_data.QueueData):
        self.env: sim.Environment = env
        self.queue_data: queue_data.QueueData = queue_data
        if queue_data.capacity == 0:
            capacity = float("inf")
        else:
            capacity = queue_data.capacity
        self._pending_put: int = 0
        super().__init__(env, capacity)

    @property
    def full(self) -> bool:
        """
        Checks if the queue is full.

        Returns:
            bool: True if the queue is full, False otherwise.
        """
        logger.debug({"ID": self.queue_data.ID, "sim_time": self.env.now, "event": f"queue has {len(self.items)} items and {self._pending_put} pending puts for capacity {self.capacity}"})
        return (self.capacity - self._pending_put - len(self.items)) <= 0
    
    def reserve(self) -> None:
        """
        Reserves a spot in the queue for a product to be put into.

        Raises:
            RuntimeError: If the queue is full.
        """
        self._pending_put += 1
        if self._pending_put + len(self.items) > self.capacity:
            raise RuntimeError("Queue is full")
    
    def unreseve(self) -> None:
        """
        Unreserves a spot in the queue for a product to be put into after the put is completed.
        """
        self._pending_put -= 1


class Storage(BaseModel):

    env: sim.Environment
    storage_data: queue_data.StorageData

    class Config:
        arbitrary_types_allowed = True

    def get_location(self) -> List[float]:
        """
        Returns the location of the resource.

        Returns:
            List[float]: The location of the resource. Has to have length 2.
        """
        return self.storage_data.location


