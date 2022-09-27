from __future__ import annotations

from abc import ABC, abstractmethod
from gc import callbacks
from typing import List
from collections.abc import Callable
from dataclasses import dataclass, field


import env
import material
import process
import resources
import request
import state

# from process import Process
import simpy


@dataclass
class Controller(ABC):
    control_policy: Callable[[List[request.Request]], None]
    _resource: resources.Resource = field(init=False)
    _env: env.Environment = field(init=False)
    requested: simpy.Event = field(init=False)

    def set_resource(self, _resource: resources.Resource) -> None:
        self._resource = _resource
        self._env = _resource._env

    def request(self, process_request: request.Request) -> None:
        self.requests.append(process_request)
        if not self.requested.triggered:
            self.requested.succeed()

    @abstractmethod
    def control_loop(self) -> None:
        pass

    @abstractmethod
    def perform_setup(
        self, _resource: resources.Resource, _process: process.Process
    ) -> None:
        pass

    @abstractmethod
    def get_next_material_for_process(
        self, _resource: resources.Resource, _process: process.Process
    ) -> List[material.Material]:
        pass

    @abstractmethod
    def sort_queue(self, _resource: resources.Resource):
        pass


class SimpleController(Controller):
    def __init__(
        self,
        _control_policy: Callable[[List[material.Material]], List[material.Material]],
        _env: env.Environment,
    ):
        self.control_policy = _control_policy
        self.requests: List[request.Request] = []
        self.running_processes: List[simpy.Event] = []
        self.requested: simpy.Event = simpy.Event(_env)

    def perform_setup(self, _resource: resources.Resource, _process: process.Process):
        _resource.setup(_process)

    def get_next_material_for_process(
        self, _resource: resources.Resource, _material: material.Material
    ):
        events = []
        for queue in _resource.input_queues:
            # _material_type = _process.get_raw_material_type()

            # TODO: here should be an advanced process model that controls, which material should be get from which
            #  queue
            events.append(queue.get(filter=lambda x: x is _material))
        return events

    def put_material_to_output_queue(
        self, _resource: resources.Resource, _materials: List[material.Material]
    ) -> None:
        events = []
        for queue in _resource.output_queues:
            # _material_type = _process.get_raw_material_type()
            # TODO: implement here a _resource.put_material_of_queues(material)
            for material in _materials:
                events.append(queue.put(material))

        return events

    def control_loop(self) -> None:
        while True:
            yield simpy.AnyOf(
                env=self._env, events=self.running_processes + [self.requested]
            )
            if self.requested.triggered:
                self.requested = simpy.Event(self._env)
            else:
                for process in self.running_processes:
                    if process.triggered:
                        self.running_processes.remove(process)

            if (
                len(self.running_processes) == self._resource.capacity
                or not self.requests
            ):
                continue

            self.control_policy(self.requests)
            process_request = self.requests.pop(0)
            running_process = self._env.process(self.start_process(process_request))
            self.running_processes.append(running_process)

    def start_process(self, process_request: request.Request):
        _resource = process_request.get_resource()
        _process = process_request.get_process()
        _material = process_request.get_material()

        # yield _resource.setup(_material.next_process)
        with _resource.request() as req:
            self.sort_queue(_resource)
            yield req
            events = self.get_next_material_for_process(_resource, _material)
            yield simpy.AllOf(_resource.env, events)
            next_materials = [event.value for event in events]
            production_state = _resource.get_free_process(_process)
            if production_state is None:
                production_state = _resource.get_process(_process)
            yield production_state.finished_process
            self.run_process(production_state, _material)
            yield production_state.finished_process
            production_state.process = None
            events = self.put_material_to_output_queue(_resource, next_materials)
            yield simpy.AllOf(_resource.env, events)
            for next_material in next_materials:
                next_material.finished_process.succeed()

    def run_process(self, input_state: state.State, target_material: material.Material):
        _env = input_state.env
        input_state.activate_state()
        input_state.state_info.log_material(target_material)
        input_state.process = _env.process(input_state.process_state())
        # return input_state.process

    def sort_queue(self, _resource: resources.Resource):
        pass


class TransportController(Controller):
    def __init__(
        self,
        _control_policy: Callable[[List[material.Material]], List[material.Material]],
        _env: env.Environment,
    ):
        self.control_policy = _control_policy
        self.requests: List[request.Request] = []
        self.running_processes: List[request.Request] = []
        self.requested: simpy.Event = simpy.Event(_env)

    def perform_setup(self, _resource: resources.Resource, _process: process.Process):
        _resource.setup(_process)

    def get_next_material_for_process(
        self, _resource: resources.Resource, _material: material.Material
    ):
        events = []
        for queue in _resource.output_queues:
            # _material_type = _process.get_raw_material_type()

            # TODO: here should be an advanced process model that controls, which material should be get from which
            #  queue
            events.append(queue.get(filter=lambda x: x is _material))
        return events

    def put_material_to_input_queue(
        self, _resource: resources.Resource, _material: material.Material
    ) -> None:
        events = []
        for queue in _resource.input_queues:
            # _material_type = _process.get_raw_material_type()
            # TODO: implement here a _resource.put_material_of_queues(material)
            events.append(queue.put(_material))

        return events

    def control_loop(self) -> None:
        while True:
            yield simpy.AnyOf(
                env=self._env, events=self.running_processes + [self.requested]
            )
            if self.requested.triggered:
                self.requested = simpy.Event(self._env)
            else:
                for process in self.running_processes:
                    if process.triggered:
                        self.running_processes.remove(process)

            if (
                len(self.running_processes) == self._resource.capacity
                or not self.requests
            ):
                continue

            self.control_policy(self.requests)
            process_request = self.requests.pop(0)
            running_process = self._env.process(self.start_process(process_request))
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

    def sort_queue(self, _resource: resources.Resource):
        pass

    def run_process(
        self,
        input_state: state.State,
        _material: material.Material,
        target: resources.Resource,
    ):
        _env = input_state.env
        target_location = target.get_location()
        input_state.activate_state()
        input_state.state_info.log_material(_material)
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
