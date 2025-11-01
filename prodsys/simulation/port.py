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

    def __init__(self, env: sim.Environment, data: port_data.QueueData):
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

    def free_space(self) -> int:
        return self.capacity - self._pending_put - len(self.items)

    @property
    def is_full(self) -> bool:
        return self._is_full()


    def reserve(self):
        """
        Reserve a slot for a future put. Waits until space is available.
        Usage: yield queue.reserve()
        """
        logger.debug(f"[RESERVE] Time={self.env.now:.2f} | Queue={self.data.ID} | Capacity={self.capacity} | Items={len(self.items)} | Pending={self._pending_put} | Full={self._is_full()}")
        self._pending_put += 1
        logger.debug(f"[RESERVE DONE] Time={self.env.now:.2f} | Queue={self.data.ID} | New Pending={self._pending_put}")

    def put(self, item) -> Generator:
        """
        Put an item; if no prior reserve(), it will implicitly wait for space.
        If caller already reserved, this will consume that reservation.
        """
        logger.debug(f"[PUT START] Time={self.env.now:.2f} | Queue={self.data.ID} | Item={item.ID} | Had Reservation={self._pending_put > 0}")
        # If caller did not reserve, wait for space now
        if self._pending_put == 0:
            while self._is_full():
                logger.debug(f"[PUT WAIT] Time={self.env.now:.2f} | Queue={self.data.ID} | Item={item.ID} | Waiting for space...")
                ev = self.on_space
                yield ev
        else:
            # consume reservation
            self._pending_put -= 1

        # Insert item
        self.items[item.ID] = item
        logger.debug(f"[PUT DONE] Time={self.env.now:.2f} | Queue={self.data.ID} | Item={item.ID} | Count={len(self.items)}/{self.capacity} | Pending={self._pending_put}")

        # Notify getters that an item is available
        self._notify("on_item")

    def get(self, item_id: str) -> Generator:
        """
        Get the specific item by ID; waits until it exists.
        Returns the item.
        """
        logger.debug(f"[GET START] Time={self.env.now:.2f} | Queue={self.data.ID} | Item={item_id} | Items={list(self.items.keys())}")
        while item_id not in self.items:
            logger.debug(f"[GET WAIT] Time={self.env.now:.2f} | Queue={self.data.ID} | Item={item_id} | Waiting...")
            ev = self.on_item
            yield ev

        item = self.items.pop(item_id)
        logger.debug(f"[GET DONE] Time={self.env.now:.2f} | Queue={self.data.ID} | Item={item_id} | Count={len(self.items)}/{self.capacity}")

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
        logger.debug(f"[GET_RESERVE START] Time={self.env.now:.2f} | Queue={self.data.ID} | Item={item_id} | Items={list(self.items.keys())} | Pending={self._pending_put}")
        # Wait for item to exist
        while item_id not in self.items:
            logger.debug(f"[GET_RESERVE WAIT] Time={self.env.now:.2f} | Queue={self.data.ID} | Item={item_id} | Waiting...")
            ev = self.on_item
            yield ev
        
        # Remove item (frees space)
        item = self.items.pop(item_id)
        logger.debug(f"[GET_RESERVE POPPED] Time={self.env.now:.2f} | Queue={self.data.ID} | Item={item_id} | Count after pop={len(self.items)}")
        
        # CRITICAL: Reserve BEFORE notifying on_space to minimize race window
        # After removing item, space is available. Reserve it immediately.
        # This prevents other processes from grabbing the freed space between
        # the get() and reserve() operations.
        self.reserve()
        logger.debug(f"[GET_RESERVE RESERVED] Time={self.env.now:.2f} | Queue={self.data.ID} | Item={item_id} | New Pending={self._pending_put}")
        
        # Now notify on_space - but queue is effectively full again (reserved)
        if self.capacity != float("inf"):
            self._notify("on_space")
        
        logger.debug(f"[GET_RESERVE DONE] Time={self.env.now:.2f} | Queue={self.data.ID} | Item={item_id}")
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
    
    def reserve(self):
        """
        Reserves a spot in the queue for a product to be put into.

        Raises:
            RuntimeError: If the queue is full.
        """
        self.store.reserve()