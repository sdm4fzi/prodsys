from __future__ import annotations

from typing import List, TYPE_CHECKING, Optional

from pydantic import BaseModel, parse_obj_as

from prodsys.simulation import sim, store

if TYPE_CHECKING:
    from prodsys.adapters import adapter
    from prodsys.models import queue_data

class QueueFactory(BaseModel):
    """
    Factory class that creates and stores `prodsys.simulation` queue objects from `prodsys.models` queue objects.

    Args:
        env (sim.Environment): prodsys simulation environment.


    Returns:
        _type_: _description_
    """
    env: sim.Environment

    queues: List[store.Queue] = []

    class Config:
        arbitrary_types_allowed = True

    def create_queues(self, adapter: adapter.ProductionSystemAdapter):
        """
        Creates queue objects based on the given adapter.

        Args:
            adapter (adapter.ProductionSystemAdapter): _description_
        """
        for queue_data in adapter.queue_data:
            self.add_queue(queue_data)

    def add_queue(self, queue_data: queue_data.QueueData):
        values = {}
        values.update({"env": self.env, "queue_data": queue_data})
        q = store.Queue(self.env, queue_data)
        self.queues.append(q)

    def get_queue(self, ID: str) -> store.Queue:
        """
        Metthod returns a queue object with the given ID.

        Args:
            ID (str): ID of the queue object.
        Returns:
            store.Queue: Queue object with the given ID.
        """
        return [q for q in self.queues if q.queue_data.ID == ID].pop()

    def get_queues(self, IDs: List[str]) -> List[store.Queue]:
        """
        Method returns a list of queue objects with the given IDs.

        Args:
            IDs (List[str]): List of IDs of the queue objects.

        Returns:
            List[store.Queue]: List of queue objects with the given IDs.
        """
        return [q for q in self.queues if q.queue_data.ID in IDs]
    


class StorageFactory(BaseModel):
    """
    Factory class that creates and stores `prodsys.simulation` queue objects from `prodsys.models` queue objects.

    Args:
        env (sim.Environment): prodsys simulation environment.


    Returns:
        _type_: _description_
    """
    env: sim.Environment

    storages: List[store.Queue] = []

    class Config:
        arbitrary_types_allowed = True

    def create_storages(self, adapter: adapter.ProductionSystemAdapter):
        """
        Creates queue objects based on the given adapter.

        Args:
            adapter (adapter.ProductionSystemAdapter): _description_
        """
        for data in adapter.storage_data:
            self.add_storage(data)

    def add_storage(self, storage_data: queue_data.StorageData):
        values = {}
        values.update({"env": self.env, "data": storage_data})
        storage_object = parse_obj_as(store.Storage, values)

        self.storages.append(storage_object)
    

    def get_storage(self, ID: str) -> Optional[store.Storage]:
        """
        Returns a process object based on the given ID.

        Args:
            ID (str): ID of the process object.

        Raises:
            ValueError: If the process object is not found.

        Returns:
            Optional[process.PROCESS_UNION]: Process object based on the given ID.
        """
        pr = [pr for pr in self.storages if pr.data.ID in ID]
        if not pr:
            raise ValueError(f"Process with ID {ID} not found")
        return pr.pop()
