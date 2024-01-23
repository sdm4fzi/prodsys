from prodsys.models.core_asset import CoreAsset
from pydantic import validator, conlist, root_validator

class LinkData(CoreAsset):
        """
        Represents a link data object between two nodes.

        Attributes:
                from_position (List[float]): The starting position of the link.
                to_position (List[float]): The ending position of the link.
        """

        from_position: conlist(float, min_items=2, max_items=2)
        to_position: conlist(float, min_items=2, max_items=2)

        class Config:
                schema_extra = {
                        "example": {
                                "ID": "Example ID",
                                "description": "Description of the link",
                                "from_position": [0, 0],
                                "to_position": [1, 1],
                        }
                }

class Node(CoreAsset):
        """
        Represents a node data object of a link.

        Attributes:
                location (List[float]): Location of the node. It has to be a list of length 2.
        """

        location = conlist(float, min_items=2, max_items=2)

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