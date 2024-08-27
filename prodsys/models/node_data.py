"""
NodeData objects are used in prodsys to represent Locations in the production system that serve as nodes in a link. They are used in the 
`LinkTransportProcess` class to represent locations where routes can cross.
"""
from hashlib import md5
from typing import List

from pydantic import ConfigDict, conlist

from prodsys.models.core_asset import CoreAsset

class NodeData(CoreAsset):
    """
    Represents a node data object of a link.

    Attributes:
            location (List[float]): Location of the node. It has to be a list of length 2.
    """

    location: conlist(float, min_length=2, max_length=2) # type: ignore

    def hash(self) -> str:
        """
        Hashes the node data object.

        Returns:
            str: Hash of the node data object.
        """
        return md5("".join([*map(str, self.location)]).encode("utf-8")).hexdigest()
    
    model_config = ConfigDict(json_schema_extra= {
        "examples": [
            {
                "ID": "N1",
                "description": "Node 1",
                "location": [0.0, 0.0],
            }
        ]
    })

