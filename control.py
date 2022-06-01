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
        print(_resource.ID, "__", id(_resource))
        for queue in _resource.input_queues:
            # _material_type = _process.get_raw_material_type()
            # TODO: here should be an advanced process model that controls, which material should be get from which queue
            print("___", _resource.input_queues[0].items)
            events.append(queue.get())
        return events

    def put_material_to_output_queue(self, _resource: resource.Resource, _material: material.Material) -> None:
        events = []
        for queue in _resource.output_queues:
            # _material_type = _process.get_raw_material_type()
            # TODO: implement here a _resource.put_material_of_queues(material)
            events.append(queue.put(_material))

    def wrap_wait_for_state_change(self) -> None:
        pass

    def request(self, _process: process.Process, _resource: resource.Resource):
        events = self.get_next_material_for_process(_resource, _process)
        yield simpy.AllOf(_resource.env, events)

        print(len(events))
        print("received material: ")
        next_materials = [event.value for event in events]
        print(type(next_materials), next_materials)
        with _resource.request() as req:
            self.sort_queue(_resource)
            yield req
            # TODO: implement setup of resources in case of a process change
            # yield _resource.setup(_material.next_process)
            print("start processing")
            yield _resource.run_process(_process)
            print("finished processing")
            state_process = _resource.get_process(_process)
            state_process.process = None
            self.put_material_to_output_queue(_resource, next_materials)
            print("__________________________")
            print(len(next_materials))
            for next_material in next_materials:
                next_material.finished_process.succeed()

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
        with _resource.request() as req:
            self.sort_queue(_resource)
            # TODO: hier Logik integrieren, dass mehrere Request in einer Liste mit einer festen Länge, die der gewählten Batchsize entspricht geyielded werden
            yield simpy.AllOf(self.registered_requests)
            # TODO: implement setup of resources in case of a process change
            yield _resource.setup(material.next_process)
            yield _resource.run_process(material.next_process)
            state_process = _resource.get_process(_process)
            del state_process.process
            material.finished_process.succeed()

    def sort_queue(self, _resource: resource.Resource):
        pass

    def check_resource_available(self):
        pass