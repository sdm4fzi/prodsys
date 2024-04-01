from __future__ import annotations

import copy
from typing import Dict, List, Optional, Union, Tuple, TYPE_CHECKING

from pydantic import BaseModel, parse_obj_as

from prodsys.simulation import sim
from prodsys.simulation import process, state
from prodsys.util.util import get_class_from_str


from prodsys.models.resource_data import (
    RESOURCE_DATA_UNION,
    ProductionResourceData,
    ControllerEnum,
    ResourceControlPolicy, TransportControlPolicy, NodeData
)
from prodsys.factories import process_factory, state_factory, queue_factory

from prodsys.simulation import control, resources

if TYPE_CHECKING:
    from prodsys.simulation import store
    from prodsys.adapters import adapter

class NodeFactory(BaseModel):
    """
    Factory class that creates and stores `prodsys.simulation` resource objects from `prodsys.models` resource objects.

    Args:
        env (sim.Environment): prodsys simulation environment.
        process_factory (process_factory.ProcessFactory): Factory that creates process objects.
        state_factory (state_factory.StateFactory): Factory that creates state objects.
        queue_factory (queue_factory.QueueFactory): Factory that creates queue objects.
    """
    env: sim.Environment
    
    nodes_data: List[NodeData] = []
    nodes: List[resources.NodeSimulationWrapper] = []
    

    class Config:
        arbitrary_types_allowed = True

    def create_nodes(self, adapter: adapter.ProductionSystemAdapter):
        """
        Creates node objects based on the given adapter.

        Args:
            adapter (adapter.ProductionSystemAdapter): Adapter that contains the node data.
        """
        
        for node_data in adapter.nodes_data:
            self.nodes.append(
                parse_obj_as(NodeData, node_data))

    def get_node(self, ID: str) -> resources.NodeSimulationWrapper:
        """
        Method returns a node object with the given ID.

        Args:
            ID (str): ID of the node object.

        Returns:
            resources.NodeSimulationWrapper: Node object with the given ID.
        """
        return [n for n in self.nodes if n.ID == ID].pop()
