from __future__ import annotations
from typing import Any, Generator, List, Literal, Union


from simpy.resources import store

import logging

logger = logging.getLogger(__name__)

from prodsys.models import port_data

from prodsys.simulation import sim
from simpy import events



class Queue:
    """
    Bounded (or unbounded) queue keyed by item.ID with explicit reservation.
    Uses two condition events:
      - on_item: fired when a new item arrives (unblocks getters)
      - on_space: fired when space frees up (unblocks putters/reservers)
    """

    def __init__(self, env: sim.Environment, data):
        self.env: sim.Environment = env
        self.data = data
        self.capacity: float = float("inf") if getattr(data, "capacity", 0) == 0 else int(data.capacity)
        self._pending_put: int = 0                  # reserved slots not yet filled
        self.items: dict[str, Any] = {}
        # Separate condition events
        self.on_item: events.Event = self.env.event()
        self.on_space: events.Event = self.env.event()

    # ---- helpers ------------------------------------------------------------
    def _is_full(self) -> bool:
        if self.capacity == float("inf"):
            return False
        return (self.capacity - self._pending_put - len(self.items)) <= 0

    def _notify(self, which: str) -> None:
        """Succeed current event (if not already), then replace it with a fresh one.
        This avoids lost wakeups while also ensuring future waiters have a new event."""
        ev: events.Event = getattr(self, which)
        if not ev.triggered:
            ev.succeed()
        setattr(self, which, self.env.event())

    # ---- API ----------------------------------------------------------------
    def reserve(self) -> Generator:
        """
        Reserve a slot for a future put. Waits until space is available.
        Usage: yield queue.reserve()
        """
        while self._is_full():
            # capture current event ref so we don't get swapped underneath
            ev = self.on_space
            yield ev
        self._pending_put += 1

    def put(self, item) -> Generator:
        """
        Put an item; if no prior reserve(), it will implicitly wait for space.
        If caller already reserved, this will consume that reservation.
        """
        # If caller did not reserve, wait for space now
        if self._pending_put == 0:
            while self._is_full():
                ev = self.on_space
                yield ev
        else:
            # consume reservation
            self._pending_put -= 1

        # Insert item
        self.items[item.ID] = item
        # print(f"[DEBUG QUEUE PUT] Time={self.env.now:.2f} | Queue={self.data.ID} | Item={item.ID} | Count={len(self.items)}/{self.capacity}")

        # Notify getters that an item is available
        self._notify("on_item")

    def get(self, item_id: str) -> Generator:
        """
        Get the specific item by ID; waits until it exists.
        Returns the item.
        """
        while item_id not in self.items:
            ev = self.on_item
            yield ev

        item = self.items.pop(item_id)
        # print(f"[DEBUG QUEUE GET] Time={self.env.now:.2f} | Queue={self.data.ID} | Item={item_id} | Count={len(self.items)}/{self.capacity}")

        # Space has freed up (unless unbounded)
        if self.capacity != float("inf"):
            self._notify("on_space")

        return item

    def get_location(self) -> List[float]:
        return self.data.location

class Store(Queue):
    """
    A store is a storage object for products / auiliaries. It has a location, an input location, and an output location. The input location is the location where products are stored, and the output location is the location where products are retrieved.

    Args:
        env (simpy.Environment): The simulation environment.
        data (data.StoreData): The store data object.
    """

    def __init__(self, env: sim.Environment, data: port_data.StoreData):
        super().__init__(env, data)
        self.data: port_data.StoreData = data
        self.store_ports: List[StorePort] = []


class StorePort(Queue):
    """
    A store port is a port that is used to store products in a store. It has a location, an input location, and an output location. The input location is the location where products are stored, and the output location is the location where products are retrieved.

    Args:
        env (simpy.Environment): The simulation environment.
        data (data.StorePortData): The store port data object.
    """

    def __init__(self, env: sim.Environment, store: Store, location: List[float]):
        super().__init__(env, store.data)
        self.store = store
        self.location = location

    def get(self, item_id: str) -> Generator:
        """
        Gets a product from the store port.

        Args:
            item_id (str): The ID of the product to get.

        Yields:
            Generator: A generator that yields the product.
        """
        yield from self.store.get(item_id)

    def put(self, item) -> Generator:
        """
        Puts a product into the store port.

        Args:
            item (object): The product to be put into the store port.
        """
        yield from self.store.put(item)

    def get_location(self) -> List[float]:
        """
        Returns the location of the store port.

        Returns:
            List[float]: The location of the store port.
        """
        return self.location
    
    def reserve(self) -> Generator:
        """
        Reserves a spot in the queue for a product to be put into.

        Raises:
            RuntimeError: If the queue is full.
        """
        yield from self.store.reserve()