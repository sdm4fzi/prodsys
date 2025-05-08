from typing import Dict, Optional
from pydantic import BaseModel, ConfigDict, Field
from typing import List

import prodsys
import prodsys.models.production_system_data
from prodsys.models.performance_data import Performance
from prodsys.util.post_processing import PostProcessor


class Project(BaseModel):
    """
    A project is a container for a production system and its adapters to group them together.

    Args:
        ID (str): The project ID.
        adapters (List[prodsys.adapters.ProductionSystemData]): The adapters of the project.
        performances (Dict[str, Performance]): The performances of the project. The key is the adapter ID.
    """

    ID: str
    adapters: List[prodsys.models.production_system_data.ProductionSystemData] = []
    # TODO: maybe allow saving performances in project also for adapter_id and specific seed
    performances: Optional[Dict[str, Performance]] = {}
    post_processor: Optional[PostProcessor] = Field(default=None, exclude=True)
    # TODO: make wrapper for postprocessor for schema

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={PostProcessor: lambda v: "PostProcessor object" if v else None},
        json_schema_extra={
            "examples": [
                {
                    "ID": "Example Project",
                    "adapters": prodsys.adapters.ProductionSystemData.model_config[
                        "json_schema_extra"
                    ]["examples"],
                    "performances": {
                        "Example Adapter": Performance.model_config[
                            "json_schema_extra"
                        ]["examples"][0]
                    },
                    "post_processor": None,
                }
            ]
        },
    )
