from __future__ import annotations

import logging
from abc import ABC
from dataclasses import dataclass, field
from typing import List, Union

import simpy

from . import (base, env, logger, process, request, resources, router, sink,
               source)

logging.basicConfig(filename="example2.log", encoding="utf-8", level=logging.DEBUG)

from collections.abc import Iterable

import numpy as np


def flatten(xs):
    for x in xs:
        if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
            yield from flatten(x)
        else:
            yield x


@dataclass
class MaterialInfo:
    resource_ID: str = field(init=False)
    state_ID: str = field(init=False)
    event_time: float = field(init=False)
    activity: str = field(init=False)
    _material_ID: str = field(init=False)

    def log_finish_material(
        self,
        resource: Union[resources.Resource, sink.Sink, source.Source],
        _material: Material,
        event_time: float,
    ):
        self.resource_ID = resource.ID
        self.state_ID = resource.ID
        self.event_time = event_time
        self._material_ID = _material.ID
        self.activity = "finished material"

    def log_create_material(
        self,
        resource: Union[resources.Resource, sink.Sink, source.Source],
        _material: Material,
        event_time: float,
    ) -> None:
        self.resource_ID = resource.ID
        self.state_ID = resource.ID
        self.event_time = event_time
        self._material_ID = _material.ID
        self.activity = "created material"


@dataclass
class Material(base.IDEntity):
    env: env.Environment
    material_type: str
    process_model: process.ProcessModel
    transport_process: process.Process
    router: router.Router
    next_process: process.Process = field(default=None, init=False)
    process: simpy.Process = field(default=None, init=False)
    next_resource: env.Location = field(default=None, init=False)
    finished_process: simpy.Event = field(default=None, init=False)
    finished: bool = field(default=False, init=False)
    material_info: MaterialInfo = field(default=MaterialInfo)

    def process_material(self):
        self.finished_process = simpy.Event(self.env)
        self.material_info.log_create_material(
            resource=self.next_resource, _material=self, event_time=self.env.now
        )
        yield self.env.process(self.transport_to_queue_of_resource())
        while self.next_process:
            self.request_process()
            yield self.finished_process
            self.finished_process = simpy.Event(self.env)
            yield self.env.process(self.transport_to_queue_of_resource())
        self.material_info.log_finish_material(
            resource=self.next_resource, _material=self, event_time=self.env.now
        )
        self.finished = True

    def request_process(self) -> None:
        self.env.request_process_of_resource(
            request.Request(self.next_process, self, self.next_resource)
        )

    def request_transport(
        self,
        transport_resource: resources.Resource,
        origin_resource: env.Location,
        target_resource: env.Location,
    ) -> None:
        self.env.request_process_of_resource(
            request.TransportResquest(
                self.transport_process,
                self,
                transport_resource,
                origin_resource,
                target_resource,
            )
        )

    def set_next_process(self):
        next_possible_processes = self.process_model.get_next_possible_processes()
        if not next_possible_processes:
            self.next_process = None
            self.next_resource = self.router.get_sink(self.material_type)
        else:
            # TODO: fix deterministic problem of petri nets!!
            self.next_process = np.random.choice(next_possible_processes)

            self.process_model.update_marking_from_transition(self.next_process)
            if self.next_process == SKIP_LABEL:
                self.set_next_process()

            self.set_next_resource()

    def transport_to_queue_of_resource(self):
        origin_resource = self.next_resource
        transport_resource = self.router.get_next_resource(self.transport_process)
        self.set_next_process()

        self.request_transport(transport_resource, origin_resource, self.next_resource)
        yield self.finished_process
        self.finished_process = simpy.Event(self.env)

    def set_next_resource(self):
        self.next_resource = self.router.get_next_resource(self.next_process)


@dataclass
class ConcreteMaterial(Material):
    due_time: float = None


SKIP_LABEL = "skip"


@dataclass
class MaterialFactory:
    data: dict
    env: env.Environment
    process_factory: process.ProcessFactory
    materials: List[Material] = field(default_factory=list, init=False)
    data_collecter: logger.Datacollector = field(default=False, init=False)
    material_counter = 0

    def create_material(self, type: str, router: router.SimpleRouter):
        for _, material_type in self.data.items():
            if material_type["ID"] == type:
                material_data = material_type
        if not material_data:
            raise ValueError(f"Material {type} does not exist.")
        process_model = self.create_process_model(material_data)

        transport_processes = self.process_factory.get_process(
            material_data["transport_process"]
        )
        material = Material(
            ID=material_data["ID"] + f" instance N.{self.material_counter}",
            description=material_data["description"],
            env=self.env,
            router=router,
            process_model=process_model,
            transport_process=transport_processes,
            material_type=type,
            material_info=MaterialInfo(),
        )
        self.data_collecter.register_patch(
            material.material_info,
            attr=["log_create_material", "log_finish_material"],
            post=logger.post_monitor_material_info,
        )

        self.material_counter += 1
        self.materials.append(material)
        return material

    def create_process_model(self, material_data) -> process.ProcessModel:
        data = material_data["processes"]
        if type(data) == list:
            process_list = self.process_factory.get_processes_in_order(
                material_data["processes"]
            )
            return process.ListProcessModel(process_list=process_list)
        if type(data) == str:
            import pm4py

            net, initial_marking, final_marking = pm4py.read_pnml(data)
            for transition in net.transitions:
                if not transition.label:
                    transition_process = SKIP_LABEL
                else:
                    transition_process = self.process_factory.get_process(
                        transition.label
                    )
                transition.properties["Process"] = transition_process
            return process.PetriNetProcessModel(net, initial_marking, final_marking)

    def get_material(self, ID) -> Material:
        return [m for m in self.materials if m.ID == ID].pop()

    def get_queues(self, IDs: List[str]) -> List[Material]:
        return [m for m in self.materials if m.ID in IDs]


@dataclass
class Order(ABC, base.IDEntity):
    target_materials: List[Material]
    release_time: float
    due_time: float
    current_materials: List[Material] = field(default_factory=lambda: [], init=False)

    def add_current_material(self, material: Material):
        self.current_materials.append(material)

    def remove_current_material(self, material: Material):
        self.current_materials.remove(material)
