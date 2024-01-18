from pydantic import BaseModel, conlist, Field
from typing import List, Optional
from uuid import uuid1

class Link(BaseModel):

        from_position: conlist(float, min_items=2, max_items=2) = Field(default_factory=lambda: [0,0])
        to_position: conlist(float, min_items=2, max_items=2) =  Field(default_factory=lambda: [0,0])
        ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))