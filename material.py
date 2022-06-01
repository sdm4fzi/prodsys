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
class Material(IDEntity):
    env: env.Environment
    processes: List[process.Process]
    router: router.SimpleRouter
    next_process: process.Process = field(default=None, init=False)
    process: simpy.Process = field(default=None, init=False)
    next_resource: resource.Resource = field(default=None, init=False)
    finished_process: simpy.Event = field(default=None, init=False)

    def process_material(self):
        self.finished_process = simpy.Event(self.env)
        yield self.env.process(self.initial_placement())
        while self.next_process:
            print(self.ID, "request process", self.next_process.description, "at resource", self.next_resource.ID)

            self.next_resource.request_process(self.next_process)
            print(self.ID, "wait for process", self.next_process.description, "at resource", self.next_resource.ID)
            yield self.finished_process
            print(self.ID, "finished process", self.next_process.description, "at resource", self.next_resource.ID)
            self.finished_process = simpy.Event(self.env)
            print(self.ID, "transport to process", self.next_process.description)
            yield self.env.process(self.transport_to_queue_of_resource())
            print(self.ID, "arrived at next process", self.next_process.description)


    def set_next_process(self):
        # TODO: this method has also to be adjusted for the process model
        if not self.processes:
            self.next_process = None
        else:
            self.next_process = self.processes.pop()
            self.set_next_resource()

    def initial_placement(self):
        self.set_next_process()
        yield self.next_resource.input_queues[0].put(self)
        print("put into queue", len(self.next_resource.input_queues[0].items), id(self.next_resource))
    def transport_to_queue_of_resource(self):
        yield self.next_resource.output_queues[0].get(filter=lambda x: x is self)
        self.set_next_process()
        print(self.next_process)
        # TODO: implement here the waiting for a transport
        yield self.env.timeout(10)
        print("timeout is over")
        yield self.next_resource.input_queues[0].put(self)
        print("put into queue", self.next_resource.input_queues[0])

    def set_next_resource(self):
        self.next_resource = self.router.get_next_resource(self.next_process)


@dataclass
class ConcreteMaterial(Material):
    due_time: float = None


@dataclass
class MaterialFactory:
    data: dict
    env: env.Environment
    process_factory: process.ProcessFactory
    materials: List[Material] = field(default_factory=list, init=False)
    material_counter = 0

    def create_material(self, type: str, router: router.SimpleRouter):
        material_data = self.data['materials'][type]
        processes = self.process_factory.get_processes(material_data['processes'])
        material = Material(ID=material_data['ID'] + f"object {self.material_counter}",
                            description=material_data['description'], env=self.env,
                            router=router, processes=processes)

        self.material_counter += 1
        self.materials.append(material)
        return material

    def get_material(self, ID) -> Material:
        return [m for m in self.materials if m.ID == ID].pop()

    def get_queues(self, IDs: List[str]) -> List[Material]:
        return [m for m in self.materials if m.ID in IDs]


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
