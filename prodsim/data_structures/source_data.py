from __future__ import annotations

from typing import Literal, Union, List, Tuple, Optional

from pydantic import validator, conlist

from enum import Enum

from prodsim.data_structures.core_asset import CoreAsset


class RouterType(str, Enum):
    SimpleRouter = "SimpleRouter"
    CapabilityRouter = "CapabilityRouter"


class RoutingHeuristic(str, Enum):
    random = "random"
    shortest_queue = "shortest_queue"
    FIFO = "FIFO"


class SourceData(CoreAsset):
    location: conlist(float, min_items=2, max_items=2)
    material_type: str
    time_model_id: str
    router: RouterType
    routing_heuristic: RoutingHeuristic
    output_queues: List[str]

    class Config:
        schema_extra = {
            "example": {
                "ID": "S1",
                "description": "Source 1",
                "location": [0.0, 0.0],
                "material_type": "Material_1",
                "time_model_id": "function_time_model_4",
                "router": "SimpleRouter",
                "routing_heuristic": "shortest_queue",
                "output_queues": ["SourceQueue"],
            }
        }
