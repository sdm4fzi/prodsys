from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from collections.abc import Callable

import process
import resource
from material import Material
from process import Process
from dataclasses import dataclass
import simpy

@dataclass
class Controller(ABC):
    control_policy: Callable[List[Material], List[Material]]

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
    def get_next_material(self, _resource: resource.Resource) -> List[Material]:
        pass

    @abstractmethod
    def wrap_wait_for_state_change(self) -> None:
        pass

    @abstractmethod
    def request(self, _process: Process, material: Material, _resource: resource.Resource):
        pass

    @abstractmethod
    def sort_queue(self, _resource: resource.Resource):
        pass

    @abstractmethod
    def check_resource_available(self):
        pass


class SimpleController(Controller):

    def wrap_request_function(self, _resource: resource.Resource):
        pass

    def perform_setup(self, _resource: resource.Resource, _process: process.Process):
        _resource.setup(_process)

    def change_state(self, _resource: resource.Resource):
        pass

    def get_next_material(self, _resource: resource.Resource) -> List[Material]:
        pass

    def wrap_wait_for_state_change(self) -> None:
        pass

    def request(self, _process: Process, material: Material, _resource: resource.Resource):
        with _resource.request() as req:
            self.sort_queue(_resource)
            yield req
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


def FIFO_control_policy(current: List[Material]) -> List[Material]:
    return current.copy()


def LIFO_control_policy(current: List[Material]) -> List[Material]:
    return list(reversed(current))


def SPT_control_policy(current: List[Material]) -> List[Material]:
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

    def get_next_material(self, _resource: resource.Resource) -> List[Material]:
        pass

    def wrap_wait_for_state_change(self) -> None:
        pass

    def request(self, _process: Process, material: Material, _resource: resource.Resource):
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


def FIFO_control_policy(current: List[Material]) -> List[Material]:
    return current.copy()


def LIFO_control_policy(current: List[Material]) -> List[Material]:
    return list(reversed(current))


def SPT_control_policy(current: List[Material]) -> List[Material]:
    current.sort(key=lambda x: x.process_time)
    return list(current)