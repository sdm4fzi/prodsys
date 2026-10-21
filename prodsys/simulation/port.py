from __future__ import annotations
from typing import Any, Generator, List, Literal, Optional, Union


from simpy.resources import store

import logging

logger = logging.getLogger(__name__)

from prodsys.models import port_data

from prodsys.simulation import sim
from simpy import events


class Port:
    def __init__(self, env: sim.Environment, data: port_data.PortData):
        self.env: sim.Environment = env
        self.data = data
        self.location = data.location
        self.input_location = data.input_location
        self.output_location = data.output_location



class Queue:
    """
    Bounded (or unbounded) queue keyed by item.ID with explicit reservation.
    Uses two condition events:
      - on_item: fired when a new item arrives (unblocks getters)
      - on_space: fired when space frees up (unblocks putters/reservers)
    """

    def __init__(self, env: sim.Environment, data: port_data.QueueData):
        self.env: sim.Environment = env
        self.data = data
        self.capacity: float = float("inf") if getattr(data, "capacity", 0) == 0 else int(data.capacity)
        self._pending_put: int = 0                  # reserved slots not yet filled
        self.items: dict[str, Any] = {}
        #: lot places of the queue (``QueueData.lot_slots``), None = only capacity counts
        self.lot_slots: Optional[int] = getattr(data, "lot_slots", None)
        #: item id -> lot key (order) of the items that occupy a lot place
        self._lot_of: dict[str, str] = {}
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

    def free_space(self) -> int:
        return self.capacity - self._pending_put - len(self.items)

    @property
    def is_full(self) -> bool:
        return self._is_full()

    def occupied_lots(self) -> set[str]:
        """Lot keys (orders) that currently hold a lot place."""
        return set(self._lot_of.values())

    def has_lot_place(self, lot_key: Optional[str]) -> bool:
        """Can an item of lot ``lot_key`` be put without exceeding the lot places?

        Items without a lot key and queues without ``lot_slots`` are never limited;
        an item joins the place of its lot if the lot already holds one.
        """
        if self.lot_slots is None or lot_key is None:
            return True
        occupied = self.occupied_lots()
        return lot_key in occupied or len(occupied) < self.lot_slots

    def _release_lot_place(self, item_id: str) -> None:
        if self._lot_of.pop(item_id, None) is not None and self.capacity == float("inf"):
            # bounded queues notify on every get anyway
            self._notify("on_space")


    def reserve(self):
        """
        Reserve a slot for a future put. 
        """
        self._pending_put += 1

    def put(
        self, item, lot_key: Optional[str] = None, wait_for_lot_place: bool = False
    ) -> Generator:
        """
        Put an item; if no prior reserve(), it will implicitly wait for space.
        If caller already reserved, this will consume that reservation.

        ``lot_key``: lot (order) of the item; with ``lot_slots`` the item occupies the
        place of its lot until it is taken out again. ``wait_for_lot_place``: wait until
        the lot has a place (blocking put of a producing resource into its output).
        """
        if wait_for_lot_place:
            while not self.has_lot_place(lot_key):
                yield self.on_space
        gate = getattr(self, "lot_slot_gate", None)
        if gate is not None:
            gate.on_put(item)
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
        if self.lot_slots is not None and lot_key is not None:
            self._lot_of[item.ID] = lot_key

        # Notify getters that an item is available
        self._notify("on_item")

    def get(self, item_id: str) -> Generator:
        """
        Get the specific item by ID; waits until it exists.
        Returns the item.
        """
        while item_id not in self.items:
            print(f"Item {item_id} not in queue {self.data.ID}")
            ev = self.on_item
            yield ev

        item = self.items.pop(item_id)
        self._release_lot_place(item_id)

        # Space has freed up (unless unbounded)
        if self.capacity != float("inf"):
            self._notify("on_space")

        return item
    
    def get_and_reserve_return(self, item_id: str):
        """
        Get an item AND immediately reserve a slot for its return.
        This minimizes race conditions for INPUT_OUTPUT queues.
        
        For INPUT_OUTPUT queues with capacity 1:
        - Item is in queue (full)
        - Get removes item (notifies on_space, wakes waiting processes)
        - Immediately reserve return slot
        - If reservation happens fast enough, queue appears full again (reserved),
          preventing other items from being put
        
        Args:
            item_id (str): The ID of the item to get.
            
        Yields:
            Generator: Yields until item is retrieved and return slot is reserved.
        """
        # Wait for item to exist
        while item_id not in self.items:
            ev = self.on_item
            yield ev
        
        # Remove item (frees space)
        item = self.items.pop(item_id)
        self._release_lot_place(item_id)
        
        # CRITICAL: Reserve BEFORE notifying on_space to minimize race window
        # After removing item, space is available. Reserve it immediately.
        # This prevents other processes from grabbing the freed space between
        # the get() and reserve() operations.
        self.reserve()
        
        # Now notify on_space - but queue is effectively full again (reserved)
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

    def put(
        self, item, lot_key: Optional[str] = None, wait_for_lot_place: bool = False
    ) -> Generator:
        """
        Puts a product into the store port.

        Args:
            item (object): The product to be put into the store port.
            lot_key (Optional[str]): Lot (order) of the product, see :meth:`Queue.put`.
            wait_for_lot_place (bool): Wait for a lot place of the store, see :meth:`Queue.put`.
        """
        yield from self.store.put(item, lot_key=lot_key, wait_for_lot_place=wait_for_lot_place)

    def has_lot_place(self, lot_key: Optional[str]) -> bool:
        return self.store.has_lot_place(lot_key)

    def get_location(self) -> List[float]:
        """
        Returns the location of the store port.

        Returns:
            List[float]: The location of the store port.
        """
        return self.location
    
    def reserve(self):
        """
        Reserves a spot in the queue for a product to be put into.

        Raises:
            RuntimeError: If the queue is full.
        """
        self.store.reserve()