from __future__ import annotations

from typing import List, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, TypeAdapter


from prodsys.models.node_data import NodeData
from prodsys.simulation import node

if TYPE_CHECKING:
    from prodsys.adapters import adapter
    from prodsys.simulation import sim


class NodeFactory:
    """
    Factory class that creates and stores `prodsys.simulation` resource objects from `prodsys.models` node objects.

    Args:
        env (sim.Environment): prodsys simulation environment.
    """

    def __init__(self, env: sim.Environment):
        self.env = env
        self.nodes = []

    def create_nodes(self, adapter: adapter.ProductionSystemAdapter):
        """
        Creates node objects based on the given adapter.

        Args:
            adapter (adapter.ProductionSystemAdapter): Adapter that contains the node data.
        """
        for node_data in adapter.node_data:
            self.create_node(node_data)

    def create_node(self, node_data: NodeData):
        """
        Creates a node object based on the given node data.

        Args:
            node_data (NodeData): Node data that is used to create the node object.
        """
        values = {}
        values.update({"data": node_data})
        self.nodes.append(TypeAdapter(node.Node).validate_python(values))

    def get_node(self, ID: str) -> node.Node:
        """
        Method returns a node object with the given ID.

        Args:
            ID (str): ID of the node object.

        Returns:
            node.Node: Node object with the given ID.
        """
        return [n for n in self.nodes if n.data.ID == ID].pop()
