from __future__ import annotations

from typing import List, TYPE_CHECKING, Optional

from pydantic import BaseModel, ConfigDict

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

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def create_queues(self, adapter: adapter.ProductionSystemAdapter):
        """
        Creates queue objects based on the given adapter.

        Args:
            adapter (adapter.ProductionSystemAdapter): _description_
        """
        for data in adapter.queue_data:
            self.add_queue(data)

    def add_queue(self, data: queue_data.QueueData):
        values = {}
        values.update({"env": self.env, "data": data})
        if hasattr(data, "location"):
            q = store.Store(**values)
        else:
            q = store.Queue(**values)
        self.queues.append(q)

    def get_queue(self, ID: str) -> store.Queue:
        """
        Metthod returns a queue object with the given ID.

        Args:
            ID (str): ID of the queue object.
        Returns:
            store.Queue: Queue object with the given ID.
        """
        return [q for q in self.queues if q.data.ID == ID].pop()

    def get_queues(self, IDs: List[str]) -> List[store.Queue]:
        """
        Method returns a list of queue objects with the given IDs.

        Args:
            IDs (List[str]): List of IDs of the queue objects.

        Returns:
            List[store.Queue]: List of queue objects with the given IDs.
        """
        return [q for q in self.queues if q.data.ID in IDs]
