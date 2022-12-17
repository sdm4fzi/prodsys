from __future__ import annotations

from typing import Literal, Union, List, Tuple, Optional

from pydantic import validator

from enum import Enum

from prodsim.data_structures.core_asset import CoreAsset

class RouterType(str, Enum):
    SimpleRouter = "SimpleRouter"
    AvoidDeadlockRouter = "AvoidDeadlockRouter"

class RoutingHeuristic(str, Enum):
    random = "random"
    shortest_queue = "shortest_queue"
    FIFO = "FIFO"


class SourceData(CoreAsset):
    location: Tuple[float, float]
    material_type: str
    time_model_id: str
    router: RouterType
    routing_heuristic: RoutingHeuristic
    output_queues: List[str]
