from abc import ABC, abstractmethod
from typing import List
from collections.abc import Callable
from base2 import Material, Resource

class Controller(ABC):
    control_policy: Callable[List[Material], List[Material]]
    controlled_resources: List[Resource]

    @abstractmethod
    def request_resource(self, resource: Resource):
        pass

    @abstractmethod
    def get_next_material(self, resource: Resource) -> List[Material]:
        pass

    @abstractmethod
    def wait_for_state_change(self) -> None:
        pass


def FIFO_control_policy(current: List[Request]) -> List[Material]:
    return current.copy()

def LIFO_control_policy(current: List[Material]) -> List[Material]:
    return list(reversed(current))

def SPT_control_policy(current: List[Material]) -> List[Material]:
    current.sort(key=lambda x: x.process_time)
    print(list(process_list), id(list(process_list)))
    return  list(current)
