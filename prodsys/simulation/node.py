from __future__ import annotations

from typing import TYPE_CHECKING, List

from pydantic import BaseModel

from prodsys.models.node_data import NodeData


class Node(BaseModel):
    data: NodeData

    def get_location(self) -> List[float]:
        """
        Returns the location of the resource.

        Returns:
            List[float]: The location of the resource. Has to have length 2.
        """
        return self.data.location