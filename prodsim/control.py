from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pydantic import BaseModel, Field, validator
from gc import callbacks
from typing import List, Generator, TYPE_CHECKING

# from process import Process
import simpy
from simpy import events

from . import env, request, resources

if TYPE_CHECKING:
    from . import material, process, state


class Controller(ABC, BaseModel):
    control_policy: Callable[[List[request.Request]], None]
    envir: env.Environment

    resource: resources.Resourcex = Field(init=False, default=None)
    requested: events.Event = Field(init=False, default=None)
    requests: List[request.Request] = Field(init=False, default_factory=list)
    running_processes: List[events.Event] = []

    @validator("requested")
    def init_requested(cls, v):
        return events.Event(cls.envir)
    
    class Config:
        arbitrary_types_allowed = True

    def set_resource(self, _resource: resources.Resourcex) -> None:
        self.resource = _resource
        self.envir = _resource.env

    def request(self, process_request: request.Request) -> None:
        self.requests.append(process_request)
        if not self.requested.triggered:
            self.requested.succeed()

    @abstractmethod
    def control_loop(self) -> None:
        pass

    @abstractmethod
    def perform_setup(
        self, _resource: resources.Resourcex, process: process.Process
    ) -> None:
        pass

    @abstractmethod
    def get_next_material_for_process(
        self, _resource: resources.Resourcex, _process: process.Process
    ) -> List[material.Material]:
        pass

    @abstractmethod
    def sort_queue(self, _resource: resources.Resourcex):
        pass


class SimpleController(Controller):

    resource: resources.ProductionResource = Field(init=False, default=None)

    def perform_setup(self, resource: resources.Resourcex, process: process.PROCESS_UNION):
        resource.setup(process)

    def get_next_material_for_process(
        self, resource: resources.ProductionResource, material: material.Material
    ):
        events = []
        for queue in resource.input_queues:
            # _material_type = _process.get_raw_material_type()

            # TODO: here should be an advanced process model that controls, which material should be get from which
            #  queue
            events.append(queue.get(filter=lambda x: x is material))
        return events

    def put_material_to_output_queue(
        self, resource: resources.ProductionResource, materials: List[material.Material]
    ) -> List[events.Event]:
        events = []
        for queue in resource.output_queues:
            # _material_type = _process.get_raw_material_type()
            # TODO: implement here a _resource.put_material_of_queues(material)
            for material in materials:
                events.append(queue.put(material))

        return events

    def control_loop(self) -> Generator:
        while True:
            yield events.AnyOf(
                env=self.envir, events=self.running_processes + [self.requested]
            )
            if self.requested.triggered:
                self.requested = events.Event(self.envir)
            else:
                for process in self.running_processes:
                    if process.triggered:
                        self.running_processes.remove(process)

            if (
                len(self.running_processes) == self.resource.capacity
                or not self.requests
            ):
                continue

            self.control_policy(self.requests)
            process_request = self.requests.pop(0)
            running_process = self.envir.process(self.start_process(process_request))
            self.running_processes.append(running_process)

    def start_process(self, process_request: request.Request):
        _resource = process_request.get_resource()
        _process = process_request.get_process()
        _material = process_request.get_material()

        # yield _resource.setup(_material.next_process)
        with _resource.request() as req:
            self.sort_queue(_resource)
            yield req
            eventss = self.get_next_material_for_process(_resource, _material)
            yield events.AllOf(_resource.env, eventss)
            next_materials = [event.value for event in eventss]
            production_state = _resource.get_free_process(_process)
            if production_state is None:
                production_state = _resource.get_process(_process)
            yield production_state.finished_process
            self.run_process(production_state, _material)
            yield production_state.finished_process
            production_state.process = None
            eventss = self.put_material_to_output_queue(_resource, next_materials)
            yield events.AllOf(_resource.env, eventss)
            for next_material in next_materials:
                next_material.finished_process.succeed()

    def run_process(self, input_state: state.State, target_material: material.Material):
        _env = input_state.env
        input_state.activate_state()
        input_state.state_info.log_material(target_material)
        input_state.process = _env.process(input_state.process_state())
        # return input_state.process

    def sort_queue(self, _resource: resources.Resourcex):
        pass


class TransportController(Controller):
    resource: resources.TransportResource = Field(init=False, default=None)

    def perform_setup(self, resource: resources.Resourcex, process: process.PROCESS_UNION):
        resource.setup(process)

    def get_next_material_for_process(
        self, resource: resources.ProductionResource, material: material.Material
    ):
        events = []
        for queue in resource.output_queues:
            # TODO: here should be an advanced process model that controls, which material should be get from which
            #  queue
            events.append(queue.get(filter=lambda x: x is material))
        return events

    def put_material_to_input_queue(
        self, resource: resources.ProductionResource, material: material.Material
    ) -> List[events.Event]:
        events = []
        for queue in resource.input_queues:
            # _material_type = _process.get_raw_material_type()
            # TODO: implement here a _resource.put_material_of_queues(material)
            events.append(queue.put(material))

        return events

    def control_loop(self) -> Generator:
        while True:
            yield events.AnyOf(
                env=self.envir, events=self.running_processes + [self.requested]
            )
            if self.requested.triggered:
                self.requested = events.Event(self.envir)
            else:
                for process in self.running_processes:
                    if process.triggered:
                        self.running_processes.remove(process)

            if (
                len(self.running_processes) == self.resource.capacity
                or not self.requests
            ):
                continue

            self.control_policy(self.requests)
            process_request = self.requests.pop(0)
            running_process = self.envir.process(self.start_process(process_request))
            self.running_processes.append(running_process)

    def start_process(self, process_request: request.TransportResquest):
        _resource = process_request.get_resource()
        _process = process_request.get_process()
        _material = process_request.get_material()
        origin = process_request.get_origin()
        target = process_request.get_target()

        _resource.current_process = _process
        # TODO: implement setup of resources in case of a process change instead of this overwriting of the setup
        # yield _resource.setup(_material.next_process)
        with _resource.request() as req:
            self.sort_queue(_resource)
            yield req
            if origin.get_location() != _resource.get_location():
                transport_state = _resource.get_process(_process)
                yield transport_state.finished_process
                self.run_process(transport_state, _material, target=origin)
                yield transport_state.finished_process
                transport_state.process = None
            events = self.get_next_material_for_process(origin, _material)
            yield simpy.AllOf(_resource.env, events)
            transport_state = _resource.get_process(_process)
            yield transport_state.finished_process
            self.run_process(transport_state, _material, target=target)
            yield transport_state.finished_process
            transport_state.process = None
            events = self.put_material_to_input_queue(target, _material)
            yield simpy.AllOf(_resource.env, events)
            _material.finished_process.succeed()

    def sort_queue(self, resource: resources.Resourcex):
        pass

    def run_process(
        self,
        input_state: state.State,
        material: material.Material,
        target: resources.Resourcex,
    ):
        _env = input_state.env
        target_location = target.get_location()
        input_state.activate_state()
        input_state.state_info.log_material(material)
        input_state.state_info.log_target_location(target)
        input_state.process = _env.process(
            input_state.process_state(target=target_location)
        )

        # return input_state.process


def FIFO_control_policy(requests: List[request.Request]) -> None:
    pass


def LIFO_control_policy(requests: List[request.Request]) -> None:
    requests.reverse()


def SPT_control_policy(requests: List[request.Request]) -> None:
    requests.sort(key=lambda x: x._process.get_expected_process_time())


def SPT_transport_control_policy(requests: List[request.Request]) -> None:
    requests.sort(
        key=lambda x: x._process.get_expected_process_time(
            x.origin.get_location(), x.target.get_location()
        )
    )


class BatchController(Controller):
    pass