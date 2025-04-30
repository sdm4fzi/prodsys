from __future__ import annotations
from typing import Any, Generator, List, Union


from simpy.resources import store

import logging

logger = logging.getLogger(__name__)

from prodsys.models import queue_data

from prodsys.simulation import sim
from simpy import events


class Queue:
    """
    Class for storing products in a queue. The queue is a filter store with a limited or unlimited capacity, where product can be put and get from.

    Args:
        env (simpy.Environment): The simulation environment.
        data (data.QueueData): The queue data object.

    Attributes:
        capacity (int, optional): The capacity of the queue. If 0 in the data, the capacity is set to infinity.
        _pending_put (int): The number of products that are reserved for being put into the queue. Avoids bottleneck in the simulation.

    """

    def __init__(self, env: sim.Environment, data: queue_data.QueueData):
        self.env: sim.Environment = env
        self.data: queue_data.QueueData = data
        if data.capacity == 0:
            self.capacity = float("inf")
        else:
            self.capacity = data.capacity
        self._pending_put: int = 0
        self.items: dict[str, Any] = {}
        self.full: bool = False
        self.state_change = self.env.event()

    def put(self, item) -> Generator:
        """
        Puts a product into the queue.

        Args:
            item (object): The product to be put into the queue.
        """
        while self.full:
            yield self.state_change
        self.state_change = events.Event(self.env)
        if self._pending_put > 0:
            self._pending_put -= 1
        self.items[item.ID] = item
        self.full = (self.capacity - self._pending_put - len(self.items)) <= 0

    def get(self, item_id: str) -> Generator:
        """
        Gets a product from the queue.

        Args:
            filter (Callable): The filter function to filter the items in the queue.

        Returns:
            object: The product that was gotten from the queue.
        """
        self.items.pop(item_id)
        self.full = (self.capacity - self._pending_put - len(self.items)) <= 0
        if not self.state_change.triggered:
            self.state_change.succeed()

    # @property
    # def full(self) -> bool:
    #     """
    #     Checks if the queue is full.

    #     Returns:
    #         bool: True if the queue is full, False otherwise.
    #     """
    #     return (self.capacity - self._pending_put - self.num_items) <= 0

    def reserve(self) -> None:
        """
        Reserves a spot in the queue for a product to be put into.

        Raises:
            RuntimeError: If the queue is full.
        """
        self._pending_put += 1
        if self._pending_put + len(self.items) > self.capacity:
            raise RuntimeError("Queue is full")


class Store(Queue):
    """
    A store is a storage object for products / auiliaries. It has a location, an input location, and an output location. The input location is the location where products are stored, and the output location is the location where products are retrieved.

    Args:
        env (simpy.Environment): The simulation environment.
        data (data.StoreData): The store data object.
    """

    def __init__(self, env: sim.Environment, data: queue_data.StoreData):
        super().__init__(env, data)
        self.data: queue_data.StoreData = data

    def get_location(self):
        return self.data.location

    def get_input_location(self):
        return self.data.input_location

    def get_output_location(self):
        return self.data.output_location
