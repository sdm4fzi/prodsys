from abc import ABC, abstractmethod
from state import State
from typing import List
from base2 import Resource

class StateHandler(ABC):
    states : List[State]
    resource : Resource

    @abstractmethod
    def set_resource(self, resource: Resource):
        pass

    @abstractmethod
    def set_state(self, state: State):
        pass