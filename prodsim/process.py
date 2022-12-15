from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple, Union, Optional

from pydantic import BaseModel, Field, validator

from . import time_model
from .data_structures import processes_data
import pm4py


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


PROCESS_UNION = Union[ProductionProcess, TransportProcess]


class ProcessModel(ABC, BaseModel):
    @abstractmethod
    def get_next_possible_processes(self) -> Optional[List[PROCESS_UNION]]:
        pass

    @abstractmethod
    def update_marking_from_transition(self, chosen_process: PROCESS_UNION) -> None:
        pass

    # def look_ahead(self, process: Process, look_ahead: int) -> List[Tuple[Process]]:
    #     pass


class ListProcessModel(ProcessModel):
    process_list: List[PROCESS_UNION]
    current_marking: int = Field(default=0, init=False)

    def get_next_possible_processes(self) -> Optional[List[PROCESS_UNION]]:
        if self.current_marking == len(self.process_list):
            return None
        return [self.process_list[self.current_marking]]

    def update_marking_from_transition(self, chosen_process: PROCESS_UNION) -> None:
        self.current_marking += 1


class PetriNetProcessModel(ProcessModel):
    net: pm4py.objects.petri_net.obj.PetriNet
    initial_marking: pm4py.objects.petri_net.obj.Marking
    final_marking: pm4py.objects.petri_net.obj.Marking
    current_marking: Optional[pm4py.objects.petri_net.obj.Marking] = Field(init=False)
    poss_trans: List[pm4py.objects.petri_net.obj.PetriNet.Transition] = Field(
        init=False, default_factory=list
    )
    semantics: pm4py.objects.petri_net.semantics.ClassicSemantics = Field(
        default=pm4py.objects.petri_net.semantics.ClassicSemantics(), init=False
    )

    class Config:
        arbitrary_types_allowed = True

    @validator("current_marking")
    def set_current_marking_initially(cls, v, values):
        return values["initial_marking"]

    def get_next_possible_processes(self) -> Optional[List[PROCESS_UNION]]:
        if not self.semantics.enabled_transitions(# type: ignore            self.net, self.current_marking
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

        return list([trans.properties["Process"] for trans in self.poss_trans])

    def update_marking_from_transition(
        self, chosen_process: Union[PROCESS_UNION, str]
    ) -> None:
        import pm4py

        for trans in self.poss_trans:
            if trans.properties["Process"] == chosen_process:
                self.current_marking = pm4py.objects.petri_net.semantics.ClassicSemantics().execute(trans, self.net, self.current_marking)  # type: ignore

