from __future__ import annotations
from typing import List, Dict
from dataclasses import dataclass, field

import simpy

import base
import env


@dataclass
class Queue(simpy.FilterStore, base.IDEntity):
    _env: env.Environment
    capacity: int = field(default=1)

    def __post_init__(self):
        super(Queue, self).__init__(self._env, self.capacity)


@dataclass
class QueueFactory:
    data: Dict
    _env: env.Environment
    queues: List[Queue] = field(default_factory=list, init=False)

    def create_queues(self):
        queues: Dict = self.data['queues']
        for values in queues.values():
            self.add_queue(values)

    def add_queue(self, values: Dict):
        queue = Queue(ID=values['ID'],
                      description=values['description'],
                      _env=self._env,
                      capacity=values['capacity']
                      )
        self.queues.append(queue)

    def get_queue(self, ID) -> Queue:
        return [q for q in self.queues if q.ID == ID].pop()

    def get_queues(self, IDs: List[str]) -> List[Queue]:
        return [q for q in self.queues if q.ID in IDs]