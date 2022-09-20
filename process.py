from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Tuple, Type, Union
from copy import copy
import pm4py

from base import IDEntity
from time_model import TimeModel, TimeModelFactory
from util import get_class_from_str


@dataclass
class Process(ABC, IDEntity):
    """
    Abstract process base class
    """
    time_model: TimeModel
    # raw_material: List[material.Material]
    # target_material: List[material.Material]

    @abstractmethod
    def get_process_time(self, *args) -> float:
        pass

    @abstractmethod
    def get_expected_process_time(self, *args) -> float:
        pass

    # def get_raw_material(self):
    #     return self.raw_material


class ProductionProcess(Process):

    def get_process_time(self) -> float:
        return self.time_model.get_next_time()

    def get_expected_process_time(self) -> float:
        return self.time_model.get_expected_time()

class TransportProcess(Process):

    def get_process_time(self, origin: List[float], target: List[float]) -> float:
        return self.time_model.get_next_time(originin=origin, target=target)

    def get_expected_process_time(self, *args) -> float:
        return self.time_model.get_expected_time(*args)


PROCESS_DICT: dict = {
    'ProductionProcesses': ProductionProcess,
    'TransportProcesses': TransportProcess,
}


@dataclass
class ProcessFactory:
    data: dict
    time_model_factory: TimeModelFactory
    processes: List[Process] = field(default_factory=list)

    def create_processes(self):
        processes = self.data['processes']
        for cls_name, items in processes.items():
            cls: Type[Process] = get_class_from_str(cls_name, PROCESS_DICT)
            for values in items.values():
                self.add_processes(cls, values)

    def add_processes(self, cls: Type[Process],  values: dict):
        time_model = self.time_model_factory.get_time_model(values['time_model_id'])
        self.processes.append(cls(ID=values['ID'], description=values['description'], time_model=time_model))

    def get_processes_in_order(self, IDs: List[str]) -> List[Process]:
        processes = []
        for ID in IDs:
            for _process in self.processes:
                if _process.ID == ID:
                    processes.append(_process)

        return processes


    def get_process(self, ID: str) -> Process:
        pr = [pr for pr in self.processes if pr.ID in ID]
        if not pr:
            return None
        return pr.pop()

class ProcessModel(ABC):


    @abstractmethod
    def get_next_possible_processes(self) -> Tuple[Process]:
        pass

    @abstractmethod
    def update_marking_from_transition(self, chosen_process: Process) -> None:
        self.current_marking += 1

    # def look_ahead(self, process: Process, look_ahead: int) -> List[Tuple[Process]]:
    #     pass


@dataclass
class ListProcessModel(ProcessModel):
    process_list: List[Process]
    current_marking: int = field(default=0, init=False)


    def get_next_possible_processes(self) -> Tuple[Process]:
        if self.current_marking == len(self.process_list):
            return None
        return self.process_list[self.current_marking], 

    def update_marking_from_transition(self, chosen_process: Process) -> None:
        self.current_marking += 1

@dataclass
class PetriNetProcessModel(ProcessModel):
    net: pm4py.objects.petri_net.obj.PetriNet
    initial_marking: pm4py.objects.petri_net.obj.Marking
    final_marking: pm4py.objects.petri_net.obj.Marking
    current_marking: pm4py.objects.petri_net.obj.Marking = field(init=False)
    poss_trans: List[pm4py.objects.petri_net.obj.PetriNet.Transition] = field(init=False)
    semantics: pm4py.objects.petri_net.semantics.ClassicSemantics = field(default=pm4py.objects.petri_net.semantics.ClassicSemantics(), init=False)

    def __post_init__(self):
        self.current_marking = self.initial_marking

    def get_next_possible_processes(self) -> Tuple[Process]:
        if not self.semantics.enabled_transitions(self.net, self.current_marking):  # supports nets with possible deadlocks
            return None
        all_enabled_trans = self.semantics.enabled_transitions(self.net, self.current_marking)
        self.poss_trans = list(all_enabled_trans)   
        before = [x for x in self.poss_trans]
        self.poss_trans.sort(key=lambda x: x.name)
        if before != self.poss_trans:
            "________________________________________________"

        return [trans.properties['Process'] for trans in self.poss_trans]

    def update_marking_from_transition(self, chosen_process: Union[Process, str]) -> None:
        for trans in self.poss_trans:
            if trans.properties['Process'] == chosen_process:
                self.current_marking = pm4py.objects.petri_net.semantics.ClassicSemantics().execute(trans, self.net, self.current_marking)








