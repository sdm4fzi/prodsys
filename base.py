from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass


class Controller(ABC):
    asset = None
    heuristic = None

    @abstractmethod
    def change_state(self) -> None:
        pass

    @abstractmethod
    def get_decision(self) -> None:
        pass

class Factory(ABC):
    # TODO: add abstract factory for the creation of the env, assets and material.
    pass

class Heuristic(ABC):

    @abstractmethod
    def get(self):
        pass


class MaterialInfo(ABC):
    bom = None
    cad_representation = None
    required_processes = None # TODO: könnte auch in der BOM enthalten sein

class BaseMaterial(ABC):
    ID : int = None

    @abstractmethod
    def get_components(self):
        pass

    @abstractmethod
    def get_process_model(self):
        pass

    @abstractmethod
    def get_tasks(self):
        pass

class Material(BaseMaterial):

    def get_process_model(self):
        pass

    def get_tasks(self):
        pass

    def __init__(self, material_info: MaterialInfo):
        self.material_info: MaterialInfo = material_info
        self.tasks = None

    def get_components(self):
        pass


class Job(ABC):
    material: Material = None



class State(ABC):

    @abstractmethod
    def process(self):
        pass

    @abstractmethod
    def interrupt(self):
        pass

class ProductionState(State):

    material = None

    def process(self):
        pass

    def interrupt(self):
        pass

    def get_material(self):
        pass

class Process(ABC):
    pass

class Asset(ABC):
    id = None

class ValueCreatorAsset(ABC):

    @property
    @abstractmethod
    def state(self):
        pass

    @state.setter
    @abstractmethod
    def state(self, state: State):
        pass

    @abstractmethod
    def transform(self, material) -> None:
        pass

    @abstractmethod
    def interrupt_active_process(self) -> None:
        pass

    @abstractmethod
    def start_process(self, process: Process) -> None:
        pass

    @abstractmethod
    def get_env(self):
        pass

    @abstractmethod
    def get_activate_state(self):
        pass

    @abstractmethod
    def set_activate_state(self, state: State):
        self.state = state
