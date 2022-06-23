from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from collections.abc import Callable

import env
import material
import process
import resource
# from process import Process
from dataclasses import dataclass
import simpy
from numba import njit

@dataclass
class Controller(ABC):
    # TODO: look at the Mesa package for the implementation of their controller or data_logger
    control_policy: Callable[List[material.Material], List[material.Material]]

    @abstractmethod
    def wrap_request_function(self, _resource: resource.Resource):
        pass

    @abstractmethod
    def perform_setup(self, _resource: resource.Resource, _process: process.Process):
        pass

    @abstractmethod
    def change_state(self, _resource: resource.Resource):
        pass

    @abstractmethod
    def get_next_material_for_process(self, _resource: resource.Resource, _process: process.Process) -> List[material.Material]:
        pass

    @abstractmethod
    def wrap_wait_for_state_change(self) -> None:
        pass

    @abstractmethod
    def request(self, _process: process.Process, _resource: resource.Resource):
        pass

    @abstractmethod
    def sort_queue(self, _resource: resource.Resource):
        pass

    @abstractmethod
    def check_resource_available(self):
        pass


class SimpleController(Controller):
    def __init__(self, _control_policy: Callable[List[material.Material]]):
        self.control_policy = _control_policy
        self.next_materials = None


    def wrap_request_function(self, _resource: resource.Resource):
        pass

    def perform_setup(self, _resource: resource.Resource, _process: process.Process):
        _resource.setup(_process)

    def change_state(self, _resource: resource.Resource):
        pass

    def get_next_material_for_process(self, _resource: resource.Resource, _process: process.Process):
        events = []
        for queue in _resource.input_queues:
            # _material_type = _process.get_raw_material_type()

            # TODO: here should be an advanced process model that controls, which material should be get from which
            #  queue
            events.append(queue.get(filter=lambda x: x.next_resource is _resource))
        return events

    def put_material_to_output_queue(self, _resource: resource.Resource, _materials: List[material.Material]) -> None:
        events = []
        for queue in _resource.output_queues:
            # _material_type = _process.get_raw_material_type()
            # TODO: implement here a _resource.put_material_of_queues(material)
            for material in _materials:
                events.append(queue.put(material))

    def wrap_wait_for_state_change(self) -> None:
        pass

    def request(self, _process: process.Process, _resource: resource.Resource):
        # TODO: implement setup of resources in case of a process change instead of this overwriting of the setup
        _resource.current_process = _process
        # yield _resource.setup(_material.next_process)
        with _resource.request() as req:
            self.sort_queue(_resource)
            yield req
            events = self.get_next_material_for_process(_resource, _process)
            yield simpy.AllOf(_resource.env, events)
            next_materials = [event.value for event in events]
            yield _resource.run_process(_process)
            state_process = _resource.get_process(_process)
            state_process.process = None
            self.put_material_to_output_queue(_resource, next_materials)
            for next_material in next_materials:
                next_material.finished_process.succeed()

    def sort_queue(self, _resource: resource.Resource):
        pass

    def check_resource_available(self):
        pass

class TransportController(Controller):
    def __init__(self, _control_policy: Callable[List[material.Material]]):
        self.control_policy = _control_policy
        self.next_materials = None


    def wrap_request_function(self, _resource: resource.Resource):
        pass

    def perform_setup(self, _resource: resource.Resource, _process: process.Process):
        _resource.setup(_process)

    def change_state(self, _resource: resource.Resource):
        pass
    
    def get_next_material_for_process(self, _resource: resource.Resource, _material: material.Material):
        events = []
        for queue in _resource.output_queues:
            # _material_type = _process.get_raw_material_type()

            # TODO: here should be an advanced process model that controls, which material should be get from which
            #  queue
            events.append(queue.get(filter=lambda x: x is _material))
        return events

    def put_material_to_input_queue(self, _resource: resource.Resource, _material: material.Material) -> None:
        events = []
        for queue in _resource.input_queues:
            # _material_type = _process.get_raw_material_type()
            # TODO: implement here a _resource.put_material_of_queues(material)
            events.append(queue.put(_material))

        return events

    def wrap_wait_for_state_change(self) -> None:
        pass

    def request(self, _process: process.Process, _resource: resource.Resource, origin: resource.Resource, target: resource.Resource, 
        _material: material.Material):
        # TODO: implement setup of resources in case of a process change instead of this overwriting of the setup
        _resource.current_process = _process
        # yield _resource.setup(_material.next_process)
        with _resource.request() as req:
            self.sort_queue(_resource)
            yield req
            yield _resource.run_transport(process=_process, target=origin.get_location())
            state_process = _resource.get_process(_process)
            state_process.process = None
            events = self.get_next_material_for_process(origin, _material)
            yield simpy.AllOf(_resource.env, events)
            yield _resource.run_transport(process=_process, target=target.get_location())
            state_process = _resource.get_process(_process)
            state_process.process = None
            events = self.put_material_to_input_queue(target, _material)
            yield simpy.AllOf(_resource.env, events)
            _material.finished_process.succeed()


    def sort_queue(self, _resource: resource.Resource):
        pass

    def check_resource_available(self):
        pass


def FIFO_control_policy(current: List[material.Material]) -> List[material.Material]:
    return current.copy()


def LIFO_control_policy(current: List[material.Material]) -> List[material.Material]:
    return list(reversed(current))


def SPT_control_policy(current: List[material.Material]) -> List[material.Material]:
    current.sort(key=lambda x: x.process_time)
    return list(current)


class BatchController(Controller):

    def reqister_request(self):
        pass

    def wrap_request_function(self, _resource: resource.Resource):
        pass

    def perform_setup(self, _resource: resource.Resource, _process: process.Process):
        _resource.setup(_process)

    def change_state(self, _resource: resource.Resource):
        pass

    def get_next_material(self, _resource: resource.Resource) -> List[material.Material]:
        pass

    def wrap_wait_for_state_change(self) -> None:
        pass

    def request(self, _process: process.Process, material: material.Material, _resource: resource.Resource):
        pass
        # TODO: hier Logik integrieren, dass mehrere Request in einer Liste mit einer festen Länge, die der gewählten Batchsize entspricht geyielded werden


    def sort_queue(self, _resource: resource.Resource):
        pass

    def check_resource_available(self):
        pass