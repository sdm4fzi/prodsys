from __future__ import annotations

from typing import Literal, Union, List, Tuple, Optional

from pydantic import validator, conlist

from enum import Enum

from prodsys.models.core_asset import CoreAsset


class RouterType(str, Enum):
    """
    Enum that represents the router type of a source.
    """
    SimpleRouter = "SimpleRouter"
    CapabilityRouter = "CapabilityRouter"


class RoutingHeuristic(str, Enum):
    """
    Enum that represents the routing heuristic of a source.
    """
    random = "random"
    shortest_queue = "shortest_queue"
    FIFO = "FIFO"


class SourceData(CoreAsset):
    """
    Class that represents a source.

    Args:
        ID (str): ID of the source.
        description (str): Description of the source.
        location (List[float]): Location of the source. It has to be a list of length 2.
        product_type (str): Product type of the source.
        time_model_id (str): Time model ID of the source.
        router (RouterType): Router of the source.
        routing_heuristic (RoutingHeuristic): Routing heuristic of the source.
        output_queues (Optional[List[str]], optional): List of output queues of the source. Defaults to None.

    Examples:
        A source with ID "S1":
        ``` py
        import prodsys
        prodsys.source_data.SourceData(
            ID="S1",
            description="Source 1",
            location=[0.0, 0.0],
            product_type="Product_1",
            time_model_id="function_time_model_4",
            router="SimpleRouter",
            routing_heuristic="shortest_queue",
            output_queues=["SourceQueue"],
        )
    """
    location: conlist(float, min_items=2, max_items=2)
    product_type: str
    time_model_id: str
    router: RouterType
    routing_heuristic: RoutingHeuristic
    output_queues: Optional[List[str]]

    class Config:
        schema_extra = {
            "example": {
                "summary": "Source",
                "value": {
                    "ID": "S1",
                    "description": "Source 1",
                    "location": [0.0, 0.0],
                    "product_type": "Product_1",
                    "time_model_id": "function_time_model_4",
                    "router": "SimpleRouter",
                    "routing_heuristic": "shortest_queue",
                    "output_queues": ["SourceQueue"],
                },
            }
        }
