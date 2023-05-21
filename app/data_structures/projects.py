from typing import Dict
from pydantic import BaseModel

import prodsys


class Project(BaseModel):
    ID: str
    adapters: Dict[str, prodsys.adapters.JsonProductionSystemAdapter] = {}

    class Config:
        schema_extra = {
            "example": {
                "summary": "Example Project",
                "value": {
                    "ID": "Example Project",
                    "adapters": {
                        "Example Adapter": prodsys.adapters.ProductionSystemAdapter.Config.schema_extra["example"]
                        
                    },
                },
            }
        }
