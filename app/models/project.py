from typing import Dict, Optional
from pydantic import BaseModel, ConfigDict
from typing import List

import prodsys
from prodsys.models.performance_data import Performance


class Project(BaseModel):
    """
    A project is a container for a production system and its adapters to group them together.

    Args:
        ID (str): The project ID.
        adapters (List[prodsys.adapters.JsonProductionSystemAdapter]): The adapters of the project.
        performances (Dict[str, Performance]): The performances of the project. The key is the adapter ID.
    """
    ID: str
    adapters: List[prodsys.adapters.JsonProductionSystemAdapter] = []
    # TODO: maybe allow saving performances in project also for adapter_id and specific seed
    performances: Optional[Dict[str, Performance]] = {}

    model_config=ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ID": "Example Project",
                    "adapters": prodsys.adapters.ProductionSystemAdapter.model_config["json_schema_extra"]["examples"],
                    "performances": {
                        "Example Adapter": Performance.Config.schema_extra["examples"][0]
                    }
                }
            ]
        }
    )