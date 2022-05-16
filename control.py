from abc import ABC, abstractmethod
from typing import List
from collections.abc import Callable
from resource import Resource
from material import Material

class Controller(ABC):
    control_policy: Callable[List[Material], List[Material]]
    controlled_resources: List[Resource]

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


def FIFO_control_policy(current: List[Material]) -> List[Material]:
    return current.copy()


def LIFO_control_policy(current: List[Material]) -> List[Material]:
    return list(reversed(current))


def SPT_control_policy(current: List[Material]) -> List[Material]:
    current.sort(key=lambda x: x.process_time)
    return list(current)
