from __future__ import annotations

from abc import ABC
from asyncio import transports
from dataclasses import dataclass, field
from typing import List

from base import IDEntity
import env
import simpy
import resource
import router
import process

from collections.abc import Iterable


def flatten(xs):
    for x in xs:
        if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
            yield from flatten(x)
        else:
            yield x


@dataclass
class Material(IDEntity):
    env: env.Environment
    processes: List[process.Process]
    transport_process: process.Process
    router: router.SimpleRouter
    next_process: process.Process = field(default=None, init=False)
    process: simpy.Process = field(default=None, init=False)
    next_resource: resource.Resource = field(default=None, init=False)
    finished_process: simpy.Event = field(default=None, init=False)
    finished: bool = field(default=False, init=False)

    def process_material(self):
        self.finished_process = simpy.Event(self.env)
        yield self.env.process(self.initial_placement())
        while self.next_process:
            self.next_resource.request_process(self.next_process)
            yield self.finished_process
            self.finished_process = simpy.Event(self.env)
            yield self.env.process(self.transport_to_queue_of_resource())
        # print(self.ID, "finished at", self.env.now)
        self.finished = True

    def set_next_process(self):
        # TODO: this method has also to be adjusted for the process model
        if not self.processes:
            self.next_process = None
        else:
            self.next_process = self.processes.pop()
            self.set_next_resource()


    def initial_placement(self):
        self.set_next_process()
        # print(self.ID, "put", self.next_resource.ID,  "before initial", len(self.next_resource.input_queues[0].items))
        yield self.next_resource.input_queues[0].put(self)
        # print(self.ID, "put", self.next_resource.ID,  "after initial", len(self.next_resource.input_queues[0].items))

    def transport_to_queue_of_resource(self):
        # print(self.ID, "get ", self.next_resource.ID,  "before", len(self.next_resource.output_queues[0].items))
        # print(self.next_resource.ID, [i.ID for i in self.next_resource.output_queues[0].items])
        # print(self.ID, "get ", self.next_resource.ID,  "after", len(self.next_resource.output_queues[0].items))
        origin_resource = self.next_resource
        self.set_next_process()
        if self.next_process is not None:
            # TODO: implement here the waiting for a transport and yield the get after arrival of the transport unit
            transport_resource = self.router.get_next_resource(self.transport_process)
            transport_resource.request_transport(process=self.transport_process, origin=origin_resource, target=self.next_resource, _material=self)
            yield self.finished_process
            self.finished_process = simpy.Event(self.env)

            


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
        processes = self.process_factory.get_processes_in_order(material_data['processes'])
        transport_processes = self.process_factory.get_process(material_data['transport_process'])
        material = Material(ID=material_data['ID'] + f" instance N.{self.material_counter}",
                            description=material_data['description'], env=self.env,
                            router=router, processes=processes, transport_process=transport_processes)

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
