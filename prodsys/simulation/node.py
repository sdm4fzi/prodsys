from typing import TYPE_CHECKING, List

from prodsys.models.node_data import NodeData


class Node:
    def __init__(self, data: NodeData):
        """
        Initialize the Node with the given data.

        Args:
            data (NodeData): The data for the node.
        """
        self.data = data

    def get_location(self) -> List[float]:
        """
        Returns the location of the resource.

        Returns:
            List[float]: The location of the resource. Has to have length 2.
        """
        return self.data.location
