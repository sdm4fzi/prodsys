from __future__ import annotations

from typing import List, Optional
from uuid import uuid1


from pydantic import Field
from pydantic.dataclasses import dataclass

from prodsys.models import links_data


from prodsys.express import core

from pydantic import conlist

@dataclass
class Link(core.ExpressObject):

    from_position: conlist(float, min_items=2, max_items=2) = Field(default_factory=lambda: [0,0])
    to_position: conlist(float, min_items=2, max_items=2) =  Field(default_factory=lambda: [0,0])
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))


    def to_model(self) -> links_data.LinkData:

        return links_data.LinkData(
            from_position = self.from_position,
            to_position = self.to_position,
            ID=self.ID,
            description=""
        )