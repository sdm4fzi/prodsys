from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Union, Optional, Dict
import random
from pydantic import BaseModel, Field, validator

from prodsys.simulation import process
from prodsys.util.util import flatten


class ProcessModel(ABC, BaseModel):
    @abstractmethod
    def get_next_possible_processes(self) -> Optional[List[process.PROCESS_UNION]]:
        pass

    @abstractmethod
    def update_marking_from_transition(
        self, chosen_process: process.PROCESS_UNION
    ) -> None:
        pass


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

class PrecendeGraphNode(BaseModel):
    process: process.PROCESS_UNION
    successors: Optional[List[PrecendeGraphNode]] = []
    predecessors: Optional[List[PrecendeGraphNode]] = []
    marking: bool = Field(default=False, init=False)

    def update_marking(self):
        self.marking = True


def get_predecessor_processes(target_process_id: str, adjacency_matrix: Dict[str, List[str]]) -> List[process.PROCESS_UNION]:
    predecessors = []
    for process_id, successors in adjacency_matrix.items():
        if target_process_id in successors:
            predecessors.append(process_id)
    return predecessors


def get_predecessors_adjacency_matrix(adjacency_matrix: Dict[str, List[str]]) -> Dict[str, List[str]]:
    predecessors_adjacency_matrix = {}
    for process_id in adjacency_matrix.keys():
        predecessors_adjacency_matrix[process_id] = get_predecessor_processes(process_id, adjacency_matrix)
    return predecessors_adjacency_matrix


def get_adjacency_matrix_from_edges(edges: List[List[str]]) -> Dict[str, List[str]]:
    nodes = list(set(flatten(edges)))
    adjacency_matrix = {}
    for node in nodes:
        successors = [edge[1] for edge in edges if edge[0] == node]
        adjacency_matrix[node] = successors
    return adjacency_matrix


class PrecedenceGraphProcessModel(ProcessModel):
    nodes: List[PrecendeGraphNode] = Field(default_factory=list, init=False)
    current_marking: Optional[PrecendeGraphNode] = Field(init=False)

    def __str__(self) -> str:
        adjacency_matrix = {}
        print(len(self.nodes))
        for node in self.nodes:
            adjacency_matrix[node.process.process_data.ID] = [successor.process.process_data.ID for successor in node.successors]
        return str(adjacency_matrix)


    def set_initial_marking(self):
        possible_starts = []
        for node in self.nodes:
            if not node.predecessors:
                possible_starts.append(node)
        if not possible_starts:
            raise ValueError("No initial marking found")
        self.current_marking = random.choice(possible_starts)


    def get_next_possible_processes(self) -> Optional[List[process.PROCESS_UNION]]:
        if not self.current_marking:
            self.set_initial_marking()
        possible_processes = [node.process for node in self.nodes if not node.marking and (not node.predecessors or all(n.marking for n in node.predecessors))]
        return possible_processes
    
    def update_marking_from_transition(
        self, chosen_process: process.PROCESS_UNION
    ) -> None:
        chosen_node = [node for node in self.nodes if node.process == chosen_process].pop()
        chosen_node.update_marking()
        self.current_marking = chosen_node

    def get_node_process_ids(self) -> List[str]:
        return [node.process.process_data.ID for node in self.nodes]


    def add_node(self, process: process.PROCESS_UNION, successors: List[process.PROCESS_UNION], predecessors: List[process.PROCESS_UNION]) -> None:
        print(process.process_data.ID, [successor.process_data.ID for successor in successors], [predecessor.process_data.ID for predecessor in predecessors])

        if not process.process_data.ID in self.get_node_process_ids():
            node = PrecendeGraphNode(process=process, successors=[], predecessors=[])
            self.nodes.append(node)
        else:
            node = [node for node in self.nodes if node.process == process].pop()
        
        successor_nodes: List[PrecendeGraphNode] = []
        for successor in successors:
            if successor.process_data.ID not in self.get_node_process_ids():
                print("add node to graph")
                self.add_node(successor, [], [])

            print("current nodes", [node.process.process_data.ID for node in self.nodes])
            successor_nodes.append([node for node in self.nodes if node.process == successor].pop())
        node.successors = successor_nodes

        predecessor_nodes: List[PrecendeGraphNode] = []
        for predecessor in predecessors:
            if predecessor.process_data.ID not in self.get_node_process_ids():
                self.add_node(predecessor, [], [])
            predecessor_nodes.append([node for node in self.nodes if node.process == predecessor].pop())

        node.predecessors = predecessor_nodes

if __name__ == "__main__":
    from prodsys.data_structures import time_model_data, processes_data, material_data
    from prodsys.factories import time_model_factory, process_factory, material_factory
    import prodsys
    from prodsys.simulation import router, sim
    import numpy as np
    t1 = time_model_data.FunctionTimeModelData(ID="t1", description="", distribution_function=time_model_data.FunctionTimeModelEnum.Constant, location=1, scale=0)
    t2 = time_model_data.FunctionTimeModelData(ID="t2", description="", distribution_function=time_model_data.FunctionTimeModelEnum.Constant, location=1, scale=0)
    t3 = time_model_data.FunctionTimeModelData(ID="t3", description="", distribution_function=time_model_data.FunctionTimeModelEnum.Constant, location=1, scale=0)
    t4 = time_model_data.FunctionTimeModelData(ID="t4", description="", distribution_function=time_model_data.FunctionTimeModelEnum.Constant, location=1, scale=0)

    time_models = [t1, t2, t3, t4]

    p1 = processes_data.ProductionProcessData(ID="p1", description="", time_model_id=t1.ID, type=processes_data.ProcessTypeEnum.ProductionProcesses)
    p2 = processes_data.ProductionProcessData(ID="p2", description="", time_model_id=t2.ID, type=processes_data.ProcessTypeEnum.ProductionProcesses)
    p3 = processes_data.ProductionProcessData(ID="p3", description="", time_model_id=t3.ID, type=processes_data.ProcessTypeEnum.ProductionProcesses)
    p4 = processes_data.ProductionProcessData(ID="p4", description="", time_model_id=t4.ID, type=processes_data.ProcessTypeEnum.ProductionProcesses)
    p5 = processes_data.ProductionProcessData(ID="p5", description="", time_model_id=t4.ID, type=processes_data.ProcessTypeEnum.ProductionProcesses)
    p6 = processes_data.ProductionProcessData(ID="p6", description="", time_model_id=t4.ID, type=processes_data.ProcessTypeEnum.ProductionProcesses)
    p7 = processes_data.ProductionProcessData(ID="p7", description="", time_model_id=t4.ID, type=processes_data.ProcessTypeEnum.ProductionProcesses)
    p8 = processes_data.ProductionProcessData(ID="p8", description="", time_model_id=t4.ID, type=processes_data.ProcessTypeEnum.ProductionProcesses)

    processes = [p1, p2, p3, p4, p5, p6, p7, p8]

    adapter = prodsys.adapters.JsonAdapter(ID="adapter")
    adapter.time_model_data = time_models
    adapter.process_data = processes

    time_model_factory_object = time_model_factory.TimeModelFactory()

    time_model_factory_object.create_time_models(adapter)

    process_factory_object = process_factory.ProcessFactory(time_model_factory=time_model_factory_object)
    process_factory_object.create_processes(adapter)

    processes = process_factory_object.processes

    print([process.process_data.ID for process in processes])

    adjacency_matrix = {
        "p1": ["p2", "p3", "p4"],
        "p2": ["p5"],
        "p3": ["p5"],
        "p4": ["p6"],
        "p5": ["p7"],
        "p6": ["p7"],
        "p7": [],
        "p8": ["p4"]
    }
    material_data_object = material_data.MaterialData(ID="material", description="", processes=adjacency_matrix, transport_process="p1")

    env = sim.Environment()
    material_factory_object = material_factory.MaterialFactory(process_factory=process_factory_object, env=env)
    process_model = material_factory_object.create_process_model(material_data_object)
    print("Created process Model")
    print(process_model)

    for _ in range(5):
        new_pm = process_model.copy(deep=True)
        print("_______________")
        while True:
            next_processes = new_pm.get_next_possible_processes()
            print("possible processes:", [process.process_data.ID for process in next_processes])
            if not next_processes:
                print("process model finished")
                break
            chosen_process = np.random.choice(next_processes)
            print("chosen process:", chosen_process.process_data.ID)
            new_pm.update_marking_from_transition(chosen_process)



    edges = [["p1", "p2"], ["p1", "p3"], ["p1", "p4"], ["p2", "p5"], ["p3", "p5"], ["p4", "p6"], ["p5", "p7"], ["p6", "p7"], ["p8", "p4"]]

    material_data_object = material_data.MaterialData(ID="material", description="", processes=edges, transport_process="p1")

    env = sim.Environment()
    material_factory_object = material_factory.MaterialFactory(process_factory=process_factory_object, env=env)
    process_model = material_factory_object.create_process_model(material_data_object)
    print("Created process Model")
    print(process_model)
