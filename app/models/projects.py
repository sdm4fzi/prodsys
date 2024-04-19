from typing import Dict
from pydantic import BaseModel
from typing import List

import prodsys


class Project(BaseModel):
    ID: str
    adapters: List[prodsys.adapters.JsonProductionSystemAdapter] = []

    class Config:
        schema_extra = {
            "example": {
                    "ID": "Example Project",
                    "adapters": [prodsys.adapters.ProductionSystemAdapter.Config.schema_extra["example"]],
            }
        }