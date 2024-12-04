"""
NodeData objects are used in prodsys to represent Locations in the production system that serve as nodes in a link. They are used in the 
`LinkTransportProcess` class to represent locations where routes can cross.
"""
from hashlib import md5
from typing import List

from pydantic import ConfigDict

from prodsys.models.core_asset import CoreAsset, Locatable

class NodeData(CoreAsset, Locatable):
    """
    Represents a node data object of a link for a Transport process.

    Attributes:
        ID (str): ID of the node.
        description (str): Description of the node.
        location (List[float]): Location of the node. It has to be a list of length 2.
    """

    def hash(self) -> str:
        """
        Hashes the node data object.

        Returns:
            str: Hash of the node data object.
        """
        return Locatable.hash(self)
    
    model_config = ConfigDict(json_schema_extra= {
        "examples": [
            {
                "ID": "N1",
                "description": "Node 1",
                "location": [0.0, 0.0],
            }
        ]
    })

