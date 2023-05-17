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


class MaterialInfo(BaseModel, extra=Extra.allow):
    """
    Class that represents information of the current state of a material.

    Args:
        resource_ID (str): ID of the resource that the material is currently at.
        state_ID (str): ID of the state that the material is currently at.
        event_time (float): Time of the event.
        activity (state.StateEnum): Activity of the material.
        material_ID (str): ID of the material.
        state_type (state.StateTypeEnum): Type of the state.
    """

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
        """
        Logs the finish of a material.

        Args:
            resource (Union[resources.Resource, sink.Sink, source.Source]): New resource of the material.
            _material (Material): Material that is finished.
            event_time (float): Time of the event.
        """
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
        """
        Logs the creation of a material.

        Args:
            resource (Union[resources.Resource, sink.Sink, source.Source]): New resource of the material.
            _material (Material): Material that is created.
            event_time (float): Time of the event.
        """
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
        """
        Logs the start of a process.

        Args:
            resource (resources.Resource): Resource that the material is processed at.
            _material (Material): Material that is processed.
            event_time (float): Time of the event.
            state_type (state.StateTypeEnum): Type of the state.
        """
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
        """
        Logs the end of a process.

        Args:
            resource (resources.Resource): Resource that the material is processed at.
            _material (Material): Material that is processed.
            event_time (float): Time of the event.
            state_type (state.StateTypeEnum): Type of the state.
        """
        self.resource_ID = resource.data.ID
        self.state_ID = resource.data.ID
        self.event_time = event_time
        self.material_ID = _material.material_data.ID
        self.activity = state.StateEnum.end_state
        self.state_type = state_type


Location = Union[resources.Resource, source.Source, sink.Sink]


class Material(BaseModel):
    """
    Class that represents a material in the discrete event simulation. For easier instantion of the class, use the MaterialFactory at prodsys.factories.material_factory.

    Args:
        env (sim.Environment): prodsys simulation environment.
        material_data (material_data.MaterialData): Material data that represents the meta information of the simulation material object.
        process_model (proces_models.ProcessModel): Process model that represents the required manufacturing processes and the current state of the material.
        transport_process (process.Process): Transport process that represents the required transport processes.
        material_router (router.Router): Router that is used to route the material object.
    """

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
        """
        Processes the material object in a simpy process. The material object is processed after creation until all required production processes are performed and it reaches a sink.
        """
        yield self.env.process(self.transport_to_queue_of_resource())
        while self.next_process:
            self.request_process()
            yield self.finished_process
            self.material_info.log_end_process(
                resource=self.next_resource,
                _material=self,
                event_time=self.env.now,
                state_type=state.StateTypeEnum.production,
            )
            self.finished_process = events.Event(self.env)
            yield self.env.process(self.transport_to_queue_of_resource())
        self.material_info.log_finish_material(
            resource=self.next_resource, _material=self, event_time=self.env.now
        )
        self.next_resource.register_finished_material(self)

    def request_process(self) -> None:
        """
        Requests the next production process of the material object from the next production resource by creating a request event and registering it at the environment.
        """
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
        """
        Requests the transport of the material object from the origin resource to the target resource by creating a transport request event and registering it at the environment.

        Args:
            transport_resource (resources.TransportResource): Transport resource that is used to transport the material object.
            origin_resource (Location): Location (either a resource, source or sink) where the material object is currently at.
            target_resource (Location): Location (either a resource, source or sink) where the material object is transported to.
        """
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
        """
        Sets the next process of the material object based on the current state of the material and its process model.
        """
        next_possible_processes = self.process_model.get_next_possible_processes()
        if not next_possible_processes:
            self.next_process = None
        else:
            self.next_process = np.random.choice(next_possible_processes)  # type: ignore
            self.process_model.update_marking_from_transition(self.next_process)  # type: ignore

    def transport_to_queue_of_resource(self):
        """
        Simpy process that transports the material object to the queue of the next resource.
        """
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
        """
        Sets the next resource of the material object based on the current state of the material and its process model.
        If no production process is required, the next resource is set to the sink of the material type.
        If no resource can be found with a free input queue, the material object waits until a resource is free.
        """
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
