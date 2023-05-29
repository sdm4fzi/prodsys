from __future__ import annotations


from simpy.resources import store

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




