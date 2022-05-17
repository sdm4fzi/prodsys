from abc import ABC, abstractmethod
from typing import List
from collections.abc import Callable
from resource import Resource
from material import Material
from process import Process
from dataclasses import dataclass

@dataclass
class Controller(ABC):
    control_policy: Callable[List[Material], List[Material]]

    @abstractmethod
    def wrap_request_function(self, resource: Resource):
        pass

    @abstractmethod
    def perform_setup(self, resource: Resource):
        pass

    @abstractmethod
    def change_state(self, resource: Resource):
        pass

    @abstractmethod
    def get_next_material(self, resource: Resource) -> List[Material]:
        pass

    @abstractmethod
    def wrap_wait_for_state_change(self) -> None:
        pass

    def request(self, process: Process, material: Material, resource: Resource):
        with resource.request() as req:
            self.sort_queue(resource)
            print("Controller requests resource")
            yield req
            print("Controller receicves resource and starts process")
            yield resource.run_process(material.next_process)
            state_process = resource.get_process(process)
            print("delete process")
            del state_process.process
            print("Controller finished process")
            material.finished_process.succeed()

    def sort_queue(self, resource: Resource):
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
