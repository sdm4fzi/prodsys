"""
A Node is the express object for a NodeData object in the models API. It represents a location in the production system layout, 
used for LinkTransportProcesses to specify crossroads or specific locations for transport.
"""
from typing import Optional
from uuid import uuid1


from pydantic import ConfigDict, Field, conlist
from pydantic.dataclasses import dataclass

from prodsys.express import core

from prodsys.models import node_data

@dataclass
class Node(core.ExpressObject):
        """
        Represents a node data object of a link, which is just a location in the production system layout. 

        Attributes:
                location (List[float]): Location of the node. It has to be a list of length 2.
        """
        location: conlist(float, min_length=2, max_length=2) # type: ignore
        ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

        model_config=ConfigDict(json_schema_extra= {
                "examples": [
                        {
                                "ID": "N1",
                                "description": "Node 1",
                                "location": [0.0, 0.0],
                        }
                ]
        })
                
        def to_model(self) -> node_data.NodeData:
             """
             Function returns a NodeData object from the Node object.
             """
             return node_data.NodeData(
                  ID = self.ID,
                  location=self.location,
                  description="",)