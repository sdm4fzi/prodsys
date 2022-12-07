from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple, Union, Optional

from pydantic import BaseModel, Field, validator

from . import time_model
from .data_structures import processes_data


class Process(ABC, BaseModel):
    """
    Abstract process base class
    """
    # process_data: processes_data.ProcessData
    time_model: time_model.TimeModel

    @abstractmethod
    def get_process_time(self, *args) -> float:
        pass

    @abstractmethod
    def get_expected_process_time(self, *args) -> float:
        pass


class ProductionProcess(Process):
    process_data: processes_data.ProductionProcessData

    def get_process_time(self) -> float:
        return self.time_model.get_next_time()

    def get_expected_process_time(self) -> float:
        return self.time_model.get_expected_time()


class TransportProcess(Process):
    process_data: processes_data.TransportProcessData

    def get_process_time(
        self, origin: Tuple[float, float], target: Tuple[float, float]
    ) -> float:
        return self.time_model.get_next_time(origin=origin, target=target)

    def get_expected_process_time(self, *args) -> float:
        return self.time_model.get_expected_time(*args)


PROCESS_DATA_UNION = Union[
    processes_data.ProductionProcessData, processes_data.TransportProcessData
]

PROCESS_UNION = Union[ProductionProcess, TransportProcess]

# @dataclass
# class ProcessFactory:
#     data: dict
#     time_model_factory: time_model.TimeModelFactory
#     processes: List[Process] = field(default_factory=list)

#     def create_processes(self):
#         for cls_name, items in self.data.items():
#             cls: Type[Process] = get_class_from_str(cls_name, PROCESS_DICT)
#             for values in items.values():
#                 self.add_processes(cls, values)

#     def add_processes(self, cls: Type[Process],  values: dict):
#         time_model = self.time_model_factory.get_time_model(values['time_model_id'])
#         self.processes.append(cls(ID=values['ID'], description=values['description'], time_model=time_model))

#     def get_processes_in_order(self, IDs: List[str]) -> List[Process]:
#         processes = []
#         for ID in IDs:
#             for _process in self.processes:
#                 if _process.ID == ID:
#                     processes.append(_process)

#         return processes


#     def get_process(self, ID: str) -> Process:
#         pr = [pr for pr in self.processes if pr.ID in ID]
#         if not pr:
#             return None
#         return pr.pop()


class ProcessModel(ABC, BaseModel):
    @abstractmethod
    def get_next_possible_processes(self) -> Optional[Tuple[Process]]:
        pass

    @abstractmethod
    def update_marking_from_transition(self, chosen_process: Process) -> None:
        pass

    # def look_ahead(self, process: Process, look_ahead: int) -> List[Tuple[Process]]:
    #     pass


class ListProcessModel(ProcessModel):
    process_list: List[Process]
    current_marking: int = Field(default=0, init=False)

    def get_next_possible_processes(self) -> Optional[Tuple[Process]]:
        if self.current_marking == len(self.process_list):
            return None
        return (self.process_list[self.current_marking],)

    def update_marking_from_transition(self, chosen_process: Process) -> None:
        self.current_marking += 1


class PetriNetProcessModel(ProcessModel):

    class Config:
        arbitrary_types_allowed = True

    import pm4py

    net: pm4py.objects.petri_net.obj.PetriNet
    initial_marking: pm4py.objects.petri_net.obj.Marking
    final_marking: pm4py.objects.petri_net.obj.Marking
    current_marking: pm4py.objects.petri_net.obj.Marking = Field(init=False)
    poss_trans: List[pm4py.objects.petri_net.obj.PetriNet.Transition] = Field(
        init=False
    )
    semantics: pm4py.objects.petri_net.semantics.ClassicSemantics = Field(
        default=pm4py.objects.petri_net.semantics.ClassicSemantics(), init=False
    )

    @validator("current_marking")
    def set_current_marking_initially(cls, v, values):
        return values["initial_marking"]

    def get_next_possible_processes(self) -> Optional[Tuple[Process]]:
        if not self.semantics.enabled_transitions(
            self.net, self.current_marking
        ):  # supports nets with possible deadlocks
            return None
        all_enabled_trans = self.semantics.enabled_transitions(
            self.net, self.current_marking
        )
        self.poss_trans = list(all_enabled_trans)
        before = [x for x in self.poss_trans]
        self.poss_trans.sort(key=lambda x: x.name)
        if before != self.poss_trans:
            "________________________________________________"

        return tuple([trans.properties["Process"] for trans in self.poss_trans])

    def update_marking_from_transition(
        self, chosen_process: Union[Process, str]
    ) -> None:
        import pm4py

        for trans in self.poss_trans:
            if trans.properties["Process"] == chosen_process:
                self.current_marking = pm4py.objects.petri_net.semantics.ClassicSemantics().execute(trans, self.net, self.current_marking)  # type: ignore
