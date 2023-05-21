from __future__ import annotations

from typing import List, TYPE_CHECKING

from pydantic import BaseModel

from prodsys.simulation import sim, store

if TYPE_CHECKING:
    from prodsys.adapters import adapter
    from prodsys.data_structures import queue_data

class QueueFactory(BaseModel):
    env: sim.Environment

    queues: List[store.Queue] = []
    queues_data: List[queue_data.QueueData] = []

    class Config:
        arbitrary_types_allowed = True

    def create_queues(self, adapter: adapter.ProductionSystemAdapter):
        for queue_data in adapter.queue_data:
            self.add_queue(queue_data)

    def add_queue(self, queue_data: queue_data.QueueData):
        values = {}
        values.update({"env": self.env, "queue_data": queue_data})
        # self.queues.append(parse_obj_as(store.Queue, values))
        q = store.Queue(self.env, queue_data)
        self.queues.append(q)
        # self.queues.append(parse_obj_as(store.Queue, values))
        # self.queues[-1].post_init()

    def get_queue(self, ID) -> store.Queue:
        return [q for q in self.queues if q.queue_data.ID == ID].pop()

    def get_queues(self, IDs: List[str]) -> List[store.Queue]:
        return [q for q in self.queues if q.queue_data.ID in IDs]