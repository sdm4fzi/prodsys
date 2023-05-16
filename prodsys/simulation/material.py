from __future__ import annotations

from abc import ABC
from enum import Enum
from collections.abc import Iterable
from typing import List, Union, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field, Extra

import numpy as np
from simpy import events

from prodsys.simulation import (
    process,
    request,
    router,
    resources,
    sim,
    sink,
    source,
    proces_models,
    state,
)

from prodsys.data_structures import material_data


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
    activity: state.StateEnum = Field(init=False, default=None)
    material_ID: str = Field(init=False, default=None)
    state_type: state.StateTypeEnum = Field(init=False, default=None)

    def log_finish_material(
        self,
        resource: Union[resources.Resource, sink.Sink, source.Source],
        _material: Material,
        event_time: float,
    ):
        self.resource_ID = resource.data.ID
        self.state_ID = resource.data.ID
        self.event_time = event_time
        self.material_ID = _material.material_data.ID
        self.activity = state.StateEnum.finished_material
        self.state_type = state.StateTypeEnum.sink

    def log_create_material(
        self,
        resource: Union[resources.Resource, sink.Sink, source.Source],
        _material: Material,
        event_time: float,
    ) -> None:
        self.resource_ID = resource.data.ID
        self.state_ID = resource.data.ID
        self.event_time = event_time
        self.material_ID = _material.material_data.ID
        self.activity = state.StateEnum.created_material
        self.state_type = state.StateTypeEnum.source

    def log_start_process(
        self,
        resource: resources.Resource,
        _material: Material,
        event_time: float,
        state_type: state.StateTypeEnum,
    ) -> None:
        self.resource_ID = resource.data.ID
        self.state_ID = resource.data.ID
        self.event_time = event_time
        self.material_ID = _material.material_data.ID
        self.activity = state.StateEnum.start_state
        self.state_type = state_type

    def log_end_process(
        self,
        resource: resources.Resource,
        _material: Material,
        event_time: float,
        state_type: state.StateTypeEnum,
    ) -> None:
        self.resource_ID = resource.data.ID
        self.state_ID = resource.data.ID
        self.event_time = event_time
        self.material_ID = _material.material_data.ID
        self.activity = state.StateEnum.end_state
        self.state_type = state_type


Location = Union[resources.Resource, source.Source, sink.Sink]


class Material(BaseModel):
    env: sim.Environment
    material_data: material_data.MaterialData
    process_model: proces_models.ProcessModel
    transport_process: process.TransportProcess
    material_router: router.Router

    next_process: Optional[process.PROCESS_UNION] = Field(default=None, init=False)
    process: events.Process = Field(default=None, init=False)
    next_resource: Location = Field(default=None, init=False)
    finished_process: events.Event = Field(default=None, init=False)
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
            self.material_info.log_end_process(
                resource=self.next_resource, _material=self, event_time=self.env.now, state_type=state.StateTypeEnum.production
            )
            self.finished_process = events.Event(self.env)
            yield self.env.process(self.transport_to_queue_of_resource())
        self.material_info.log_finish_material(
            resource=self.next_resource, _material=self, event_time=self.env.now
        )
        self.next_resource.register_finished_material(self)

    def request_process(self) -> None:
        if self.next_process:
            self.env.request_process_of_resource(
                request.Request(
                    process=self.next_process,
                    material=self,
                    resource=self.next_resource,
                )
            )

    def request_transport(
        self,
        transport_resource: resources.TransportResource,
        origin_resource: Location,
        target_resource: Location,
    ) -> None:
        self.env.request_process_of_resource(
            request.TransportResquest(
                process=self.transport_process,
                material=self,
                resource=transport_resource,
                origin=origin_resource,
                target=target_resource,
            )
        )

    def set_next_process(self):
        next_possible_processes = self.process_model.get_next_possible_processes()
        if not next_possible_processes:
            self.next_process = None
        else:
            self.next_process = np.random.choice(next_possible_processes)  # type: ignore
            self.process_model.update_marking_from_transition(self.next_process)  # type: ignore
            if self.next_process == SKIP_LABEL:
                self.set_next_process()

    def transport_to_queue_of_resource(self):
        origin_resource = self.next_resource
        transport_resource = self.material_router.get_next_resource(
            self.transport_process
        )
        yield self.env.timeout(0)
        self.set_next_process()
        yield self.env.process(self.set_next_resource())
        self.request_transport(transport_resource, origin_resource, self.next_resource)  # type: ignore False
        yield self.finished_process
        self.material_info.log_end_process(
            resource=transport_resource,
            _material=self,
            event_time=self.env.now,
            state_type=state.StateTypeEnum.transport,
        )
        self.finished_process = events.Event(self.env)

    def set_next_resource(self):
        if not self.next_process:
            self.next_resource = self.material_router.get_sink(
                self.material_data.material_type
            )
        else:
            self.next_resource = self.material_router.get_next_resource(
                self.next_process
            )
            while True:
                if self.next_resource is not None and isinstance(
                    self.next_resource, resources.ProductionResource
                ):
                    self.next_resource.reserve_input_queues()
                    yield self.env.timeout(0)
                    break
                resource_got_free_events = [
                    resource.got_free
                    for resource in self.material_router.get_possible_resources(
                        self.next_process
                    )
                ]
                yield events.AnyOf(self.env, resource_got_free_events)
                for resource in self.material_router.get_possible_resources(
                    self.next_process
                ):
                    if resource.got_free.triggered:
                        resource.got_free = events.Event(self.env)

                self.next_resource = self.material_router.get_next_resource(
                    self.next_process
                )
