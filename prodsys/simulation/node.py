from typing import TYPE_CHECKING, List

from prodsys.models.node_data import NodeData
from prodsys.simulation import sim

class Node:
    def __init__(self, data: NodeData, env: sim.Environment):
        """
        Initialize the Node with the given data.

        Args:
            data (NodeData): The data for the node.
            env (sim.Environment): The environment of the node.
        """
        self.env = env
        self.data = data

    def get_location(self) -> List[float]:
        """
        Returns the location of the resource.

        Returns:
            List[float]: The location of the resource. Has to have length 2.
        """
        return self.data.location
