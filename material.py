from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import List

from base import IDEntity
import env
import simpy
import resource
import router
import process


@dataclass
class Material(ABC, IDEntity):
    env: env.Environment
    # TODO: here has to be a process model class that can be requested / the router
    processes: List[process.Process]
    next_process: process.Process = field(default=None, init=False)
    process: simpy.Process = field(default=None, init=False)
    next_resource: resource.Resource = field(default=None, init=False)
    finished_process: simpy.Event = field(default=None, init=False)
    router: router.Router = field(default=None, init=False)

    def __post_init__(self):
        self.finished_process = simpy.Event(self.env)
        self.set_next_process()

    def process_material(self):
        while self.next_process:
            self.next_resource.request_process(self.next_process)
            yield self.finished_process
            self.finished_process = simpy.Event(self.env)

            self.set_next_process()

    def set_next_process(self):
        # TODO: this method has also to be adjusted for the process model
        if not self.processes:
            self.next_process = None
        else:
            self.next_process = self.processes.pop()
            self.set_next_resource()

    def set_next_resource(self):
        self.next_resource = self.router.get_next_resource(self.next_process)


@dataclass
class ConcreteMaterial(Material):
    due_time: float = None


@dataclass
class Order(ABC, IDEntity):
    target_materials: List[Material]
    release_time: float
    due_time: float
    current_materials: List[Material] = field(default_factory=lambda: [], init=False)

    def add_current_material(self, material: Material):
        self.current_materials.append(material)

    def remove_current_material(self, material: Material):
        self.current_materials.remove(material)
