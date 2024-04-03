from __future__ import annotations
from hashlib import md5
from typing import Literal, Union, List, Tuple, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from prodsys.adapters.adapter import ProductionSystemAdapter
from pydantic import validator, conlist

from enum import Enum

from prodsys.models.core_asset import CoreAsset

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
    router: str
    routing_heuristic: RoutingHeuristic
    output_queues: Optional[List[str]]
    
    def tomd5(self, adapter: ProductionSystemAdapter) -> str:
        for product in adapter.product_data:
            if product.ID == self.product_type:
                product_hash = product.tomd5(adapter)
                break

        for time_model in adapter.time_model_data:
            if time_model.ID == self.time_model_id:
                time_model_hash = time_model.tomd5()
                break

        return md5(("".join([*[str(l) for l in self.location], product_hash, time_model_hash, self.routing_heuristic])).encode("utf-8")).hexdigest()
    
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
