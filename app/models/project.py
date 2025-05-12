from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, ConfigDict, Field
from typing import List

import prodsys
from prodsys.models.performance_data import Performance
from prodsys.optimization.optimizer import HyperParameters, Optimizer
from prodsys.util.post_processing import PostProcessor


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
    performances: Optional[Dict[str, Performance]] = {}
    optimizer_hyperparameters: Optional[Dict[str, Union[HyperParameters]]] = {}
    optimizer: Optional[Dict[str, Any]] = {}

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        # json_encoders={
        #     Optimizer: lambda v: v.get_model().model_dump_json(),
        # },
        json_schema_extra={
            "examples": [
                {
                    "ID": "Example Project",
                    "adapters": prodsys.adapters.ProductionSystemAdapter.model_config["json_schema_extra"]["examples"],
                    "performances": {
                        "Example Adapter": Performance.model_config["json_schema_extra"]["examples"][0]
                    }
                }
            ]
        }
    )