from __future__ import annotations

from typing import List, TYPE_CHECKING, Optional

from prodsys.models import port_data

from prodsys.simulation import sim, store

if TYPE_CHECKING:
    from prodsys.models import production_system_data


class QueueFactory:
    """
    Factory class that creates and stores `prodsys.simulation` queue objects from `prodsys.models` queue objects.

    Args:
        env (sim.Environment): prodsys simulation environment.


    Returns:
        _type_: _description_
    """

    def __init__(self, env: sim.Environment):
        """
        Initializes the QueueFactory with the given environment.

        Args:
            env (sim.Environment): prodsys simulation environment.
        """
        self.env = env
        self.queues: list[store.Queue] = []

    def create_queues(self, adapter: production_system_data.ProductionSystemData):
        """
        Creates queue objects based on the given adapter.

        Args:
            adapter (adapter.ProductionSystemAdapter): _description_
        """
        for data in adapter.port_data:
            self.add_queue(data)

    def add_queue(self, data: port_data.QueueData | port_data.StoreData):
        values = {}
        values.update({"env": self.env, "data": data})
        if data.port_type == port_data.PortType.STORE:
            q = store.Store(**values)
            if data.port_locations is not None:
                q.store_ports = [
                    store.StorePort(
                        store=q, 
                        location=loc
                        )
                    for loc in data.port_locations
                ]
            else:
                q.store_ports = [store.StorePort(store=q, location=data.location)]
        elif data.port_type == port_data.PortType.QUEUE:
            q = store.Queue(**values)
        else:
            raise ValueError(f"Unknown port type: {data.port_type}")
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
