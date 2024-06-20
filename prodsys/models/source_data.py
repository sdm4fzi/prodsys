from __future__ import annotations
from hashlib import md5
from typing import List, Optional, TYPE_CHECKING
from pydantic import ConfigDict, conlist
from enum import Enum

from prodsys.models.core_asset import CoreAsset

if TYPE_CHECKING:
    from prodsys.adapters.adapter import ProductionSystemAdapter


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
    output_location: conlist(float, min_length=2, max_length=2) # type: ignore
    product_type: str
    time_model_id: str
    routing_heuristic: RoutingHeuristic
    output_queues: List[str] = []
    
    def hash(self, adapter: ProductionSystemAdapter) -> str:
        """
        Returns a unique hash for the source considering its location, product type, time model, routing heuristic and output queues.

        Args:
            adapter (ProductionSystemAdapter): Adapter of the production system.

        Raises:
            ValueError: If the product, time model or output queue is not found in the adapter.

        Returns:
            str: Hash of the source.
        """
        for product in adapter.product_data:
            if product.product_type == self.product_type:
                product_hash = product.hash(adapter)
                break
        else:
            raise ValueError(f"Product with ID {self.product_type} not found for source {self.ID}.")

        for time_model in adapter.time_model_data:
            if time_model.ID == self.time_model_id:
                time_model_hash = time_model.hash()
                break
        else:
            raise ValueError(f"Time model with ID {self.time_model_id} not found for source {self.ID}.")
        
        output_queue_hashes = []
        for output_queue in self.output_queues:
            for queue in adapter.queue_data:
                if queue.ID == output_queue:
                    output_queue_hashes.append(queue.hash())
                    break
            else:
                raise ValueError(f"Queue with ID {output_queue} not found for source {self.ID}.")

        return md5(("".join([*map(str, self.location), product_hash, time_model_hash, self.routing_heuristic, *sorted(output_queue_hashes)])).encode("utf-8")).hexdigest()
    
    model_config=ConfigDict(json_schema_extra={
        "examples": [
            {
                "ID": "S1",
                "description": "Source 1",
                "location": [0.0, 0.0],
                "product_type": "Product_1",
                "time_model_id": "function_time_model_4",
                "router": "SimpleRouter",
                "routing_heuristic": "shortest_queue",
                "output_queues": ["SourceQueue"],
            }
        ]
    })
