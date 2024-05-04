"""
NodeData objects are used in prodsys to represent Locations in the production system that serve as nodes in a link. They are used in the 
`LinkTransportProcess` class to represent locations where routes can cross.
"""

from __future__ import annotations

from hashlib import md5
from typing import List

from pydantic import conlist

from prodsys.models.core_asset import CoreAsset

class NodeData(CoreAsset):
    """
    Represents a node data object of a link.

    Attributes:
            location (List[float]): Location of the node. It has to be a list of length 2.
    """

    location: conlist(float, min_items=2, max_items=2) # type: ignore

    def hash(self) -> str:
        """
        Hashes the node data object.

        Returns:
            str: Hash of the node data object.
        """
        return md5("".join([*map(str, self.location)]).encode("utf-8")).hexdigest()

    class Config:
        schema_extra = {
            "example": {
                "summary": "Node",
                "value": {
                    "ID": "N1",
                    "description": "Node 1",
                    "location": [0.0, 0.0],
                },
            }
        }

