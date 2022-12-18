from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Union, Optional

from pydantic import BaseModel, Field, validator

from prodsim.simulation import process
import pm4py


class ProcessModel(ABC, BaseModel):
    @abstractmethod
    def get_next_possible_processes(self) -> Optional[List[process.PROCESS_UNION]]:
        pass

    @abstractmethod
    def update_marking_from_transition(
        self, chosen_process: process.PROCESS_UNION
    ) -> None:
        pass

    # def look_ahead(self, process: Process, look_ahead: int) -> List[Tuple[Process]]:
    #     pass


class ListProcessModel(ProcessModel):
    process_list: List[process.PROCESS_UNION]
    current_marking: int = Field(default=0, init=False)

    def get_next_possible_processes(self) -> Optional[List[process.PROCESS_UNION]]:
        if self.current_marking == len(self.process_list):
            return None
        return [self.process_list[self.current_marking]]

    def update_marking_from_transition(
        self, chosen_process: process.PROCESS_UNION
    ) -> None:
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

    @validator("current_marking", pre=True, always=True)
    def set_current_marking_initially(cls, v, values):
        return values["initial_marking"]

    def get_next_possible_processes(self) -> Optional[List[process.PROCESS_UNION]]:
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

        return list([trans.properties["Process"] for trans in self.poss_trans])

    def update_marking_from_transition(
        self, chosen_process: Union[process.PROCESS_UNION, str]
    ) -> None:
        import pm4py

        for trans in self.poss_trans:
            if trans.properties["Process"] == chosen_process:
                self.current_marking = pm4py.objects.petri_net.semantics.ClassicSemantics().execute(t=trans, pn=self.net, m=self.current_marking)  # type: ignore
