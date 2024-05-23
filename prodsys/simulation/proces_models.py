from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Dict
import random
from pydantic import BaseModel, Field

from prodsys.simulation import process
from prodsys.util.util import flatten


class ProcessModel(ABC, BaseModel):
    """
    Abstract process model base class that defines the interface for all process models.
    """

    @abstractmethod
    def get_next_possible_processes(self) -> Optional[List[process.PROCESS_UNION]]:
        """
        Returns the next possible processes.

        Returns:
            Optional[List[process.PROCESS_UNION]]: List of possible processes.
        """
        pass

    @abstractmethod
    def update_marking_from_transition(
        self, chosen_process: process.PROCESS_UNION
    ) -> None:
        """
        Updates the marking of the process model based on the chosen process.

        Args:
            chosen_process (process.PROCESS_UNION): The chosen process that is executed.
        """
        pass


class ListProcessModel(ProcessModel):
    """
    Process model that is based on a list of processes. The processes are executed sequentially in the order of the list.

    Args:
        process_list (List[process.PROCESS_UNION]): List of processes that are executed sequentially.
    """

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
    """
    Class that represents a node in a precedence graph.

    Args:
        process (process.PROCESS_UNION): The process that is represented by the node.
        successors (Optional[List[PrecendeGraphNode]]): List of successor nodes.
        predecessors (Optional[List[PrecendeGraphNode]]): List of predecessor nodes.

    Attributes:
        marking (bool): Indicates if the node is marked.
    """

    process: process.PROCESS_UNION
    successors: Optional[List[PrecendeGraphNode]] = []
    predecessors: Optional[List[PrecendeGraphNode]] = []
    marking: bool = Field(default=False, init=False)

    def update_marking(self):
        """
        Updates the marking of the node, to save that the process has been executed.
        """
        self.marking = True


def get_predecessor_processes(
    target_process_id: str, adjacency_matrix: Dict[str, List[str]]
) -> List[process.PROCESS_UNION]:
    """
    Returns the predecessing processes' IDs of a ID of a process.

    Args:
        target_process_id (str): process ID of the process for which the predecessing processes' IDs are returned.
        adjacency_matrix (Dict[str, List[str]]): Adjacency matrix of the process model. The keys are the process IDs and the values are the IDs of the successor processes.

    Returns:
        List[process.PROCESS_UNION]: List of predecessing processes' IDs.
    """
    predecessors = []
    for process_id, successors in adjacency_matrix.items():
        if target_process_id in successors:
            predecessors.append(process_id)
    return predecessors


def get_predecessors_adjacency_matrix(
    adjacency_matrix: Dict[str, List[str]]
) -> Dict[str, List[str]]:
    """
    Returns the predecessing processes' IDs of all processes in a process model.

    Args:
        adjacency_matrix (Dict[str, List[str]]): Adjacency matrix of the process model. The keys are the process IDs and the values are the IDs of the successor processes.

    Returns:
        Dict[str, List[str]]: Predecessor adjacency matrix of the process model. The keys are the process IDs and the values are the IDs of the predecessing processes.
    """
    predecessors_adjacency_matrix = {}
    for process_id in adjacency_matrix.keys():
        predecessors_adjacency_matrix[process_id] = get_predecessor_processes(
            process_id, adjacency_matrix
        )
    return predecessors_adjacency_matrix


def get_adjacency_matrix_from_edges(edges: List[List[str]]) -> Dict[str, List[str]]:
    """
    Returns the adjacency matrix of a process model from a list of edges.

    Args:
        edges (List[List[str]]): List of edges. Each edge is a list of two process IDs. The first process ID is the predecessor and the second process ID is the successor.

    Returns:
        Dict[str, List[str]]: Adjacency matrix of the process model. The keys are the process IDs and the values are the IDs of the successor processes.
    """
    nodes = list(set(flatten(edges)))
    adjacency_matrix = {}
    for node in nodes:
        successors = [edge[1] for edge in edges if edge[0] == node]
        adjacency_matrix[node] = successors
    return adjacency_matrix


class PrecedenceGraphProcessModel(ProcessModel):
    """
    Process model that is based on a precedence graph.

    Attributes:
        nodes (List[PrecendeGraphNode]): List of nodes in the precedence graph.
        current_marking (Optional[PrecendeGraphNode]): The current marking, i.e. the node that represents the previously executed process, of the process model.
    """

    nodes: List[PrecendeGraphNode] = Field(default_factory=list, init=False)
    current_marking: Optional[PrecendeGraphNode] = Field(init=False)

    def __str__(self) -> str:
        """
        Returns a string representation of the adjacency matrix of the process model.

        Returns:
            str: String representation of the adjacency matrix of the process model.
        """
        adjacency_matrix = {}
        for node in self.nodes:
            adjacency_matrix[node.process.process_data.ID] = [
                successor.process.process_data.ID for successor in node.successors
            ]
        return str(adjacency_matrix)

    def set_initial_marking(self):
        """
        Sets the initial marking of the process model. The initial marking is a node that has no predecessing nodes.

        Raises:
            ValueError: If no initial marking is found.
        """
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
        possible_processes = [
            node.process
            for node in self.nodes
            if not node.marking
            and (not node.predecessors or all(n.marking for n in node.predecessors))
        ]
        return possible_processes

    def update_marking_from_transition(
        self, chosen_process: process.PROCESS_UNION
    ) -> None:
        chosen_node = [
            node for node in self.nodes if node.process == chosen_process
        ].pop()
        chosen_node.update_marking()
        self.current_marking = chosen_node

    def get_node_process_ids(self) -> List[str]:
        """
        Returns the process IDs of all nodes in the process model.

        Returns:
            List[str]: List of process IDs of all nodes in the process model.
        """
        return [node.process.process_data.ID for node in self.nodes]

    def add_node(
        self,
        process: process.PROCESS_UNION,
        successors: List[process.PROCESS_UNION],
        predecessors: List[process.PROCESS_UNION],
    ) -> None:
        """
        Adds a node to the process model. If the processes of the successors and predecessors are not in the process model, they are added as well, with for now empty lists of successors and predecessors.

        Args:
            process (process.PROCESS_UNION): Process that is represented by the node.
            successors (List[process.PROCESS_UNION]): List of successor processes.
            predecessors (List[process.PROCESS_UNION]): List of predecessor processes.
        """
        if not process.process_data.ID in self.get_node_process_ids():
            node = PrecendeGraphNode(process=process, successors=[], predecessors=[])
            self.nodes.append(node)
        else:
            node = [node for node in self.nodes if node.process == process].pop()

        successor_nodes: List[PrecendeGraphNode] = []
        for successor in successors:
            if successor.process_data.ID not in self.get_node_process_ids():
                self.add_node(successor, [], [])

            successor_nodes.append(
                [node for node in self.nodes if node.process == successor].pop()
            )
        node.successors = successor_nodes

        predecessor_nodes: List[PrecendeGraphNode] = []
        for predecessor in predecessors:
            if predecessor.process_data.ID not in self.get_node_process_ids():
                self.add_node(predecessor, [], [])
            predecessor_nodes.append(
                [node for node in self.nodes if node.process == predecessor].pop()
            )

        node.predecessors = predecessor_nodes
