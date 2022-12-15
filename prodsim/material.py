from __future__ import annotations

from abc import ABC
from collections.abc import Iterable
from typing import List, Union, Optional

from pydantic import BaseModel, Field, Extra

import numpy as np
from simpy import events

from . import (process, request, resources, router, sim, sink,
               source)

from .data_structures import material_data


def flatten(xs):
    for x in xs:
        if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
            yield from flatten(x)
        else:
            yield x

SKIP_LABEL = "skip"

class MaterialInfo(BaseModel, extra=Extra.allow):
    resource_ID: str = Field(init=False, default=None)
    state_ID: str = Field(init=False, default=None)
    event_time: float = Field(init=False, default=None)
    activity: str = Field(init=False, default=None)
    material_ID: str = Field(init=False, default=None)

    def log_finish_material(
        self,
        resource: Union[resources.Resourcex, sink.Sink, source.Source],
        _material: Material,
        event_time: float,
    ):  
        self.resource_ID = resource.data.ID
        self.state_ID = resource.data.ID
        self.event_time = event_time
        self.material_ID = _material.material_data.ID
        self.activity = "finished material"

    def log_create_material(
        self,
        resource: Union[resources.Resourcex, sink.Sink, source.Source],
        _material: Material,
        event_time: float,
    ) -> None:
        self.resource_ID = resource.data.ID
        self.state_ID = resource.data.ID
        self.event_time = event_time
        self.material_ID = _material.material_data.ID
        self.activity = "created material"


Location = Union[resources.Resourcex, source.Source, sink.Sink]


class Material(BaseModel):
    env: sim.Environment
    material_data: material_data.MaterialData
    process_model: process.ProcessModel
    transport_process: process.TransportProcess
    router: router.Router

    next_process: Optional[process.PROCESS_UNION] = Field(default=None, init=False)
    process: events.Process = Field(default=None, init=False)
    next_resource: Location = Field(default=None, init=False)
    finished_process: events.Event = Field(default=None, init=False)
    finished: bool = False
    material_info: MaterialInfo = MaterialInfo()

    class Config:
        arbitrary_types_allowed = True

    def process_material(self):
        self.finished_process = events.Event(self.env)
        self.material_info.log_create_material(
            resource=self.next_resource, _material=self, event_time=self.env.now
        )
        yield self.env.process(self.transport_to_queue_of_resource())
        while self.next_process:
            self.request_process()
            yield self.finished_process
            self.finished_process = events.Event(self.env)
            yield self.env.process(self.transport_to_queue_of_resource())
        self.material_info.log_finish_material(
            resource=self.next_resource, _material=self, event_time=self.env.now
        )
        self.finished = True

    def request_process(self) -> None:
        if isinstance(self.next_resource, resources.Resourcex):
            if self.next_process:
                self.env.request_process_of_resource(
                    request.Request(self.next_process, self, self.next_resource)
                )
        else:
            raise TypeError("Only requests to resources are allowed!")

    def request_transport(
        self,
        transport_resource: resources.TransportResource,
        origin_resource: Location,
        target_resource: Location,
    ) -> None:
        if isinstance(origin_resource, resources.Resourcex) and isinstance(target_resource, resources.Resourcex):
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
            self.next_resource = self.router.get_sink(self.material_data.material_type)
        else:
            # TODO: fix deterministic problem of petri nets!!
            if next_possible_processes:
                self.next_process = np.random.choice(next_possible_processes) # type: ignore
            self.process_model.update_marking_from_transition(self.next_process) # type: ignore
            if self.next_process == SKIP_LABEL:
                self.set_next_process()

            self.set_next_resource()

    def transport_to_queue_of_resource(self):
        origin_resource = self.next_resource
        transport_resource = self.router.get_next_resource(self.transport_process)
        self.set_next_process()
        if isinstance(transport_resource, resources.TransportResource):
            self.request_transport(transport_resource, origin_resource, self.next_resource)
            yield self.finished_process
        self.finished_process = events.Event(self.env)

    def set_next_resource(self):
        if self.next_process:
            self.next_resource = self.router.get_next_resource(self.next_process)


class ConcreteMaterial(Material):
    due_time: float = 0.0



class Order(ABC, BaseModel):
    target_materials: List[Material]
    release_time: float
    due_time: float
    current_materials: List[Material] = Field(default_factory=lambda: [], init=False)

    def add_current_material(self, material: Material):
        self.current_materials.append(material)

    def remove_current_material(self, material: Material):
        self.current_materials.remove(material)

