from __future__ import annotations
from hashlib import md5
from typing import List, Optional, TYPE_CHECKING
from pydantic import ConfigDict, conlist
from enum import Enum

from prodsys.models.core_asset import CoreAsset, Locatable

if TYPE_CHECKING:
    from prodsys.models.production_system_data import ProductionSystemData


class RoutingHeuristic(str, Enum):
    """
    Enum that represents the routing heuristic of a source.
    """

    random = "random"
    shortest_queue = "shortest_queue"
    FIFO = "FIFO"


class SourceData(CoreAsset, Locatable):
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
        ports (Optional[List[str]], optional): List of ports of the source. Defaults to None.

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
            ports=["SourceQueue"],
        )
    """

    product_type: str
    time_model_id: str
    routing_heuristic: RoutingHeuristic
    ports: List[str] = []

    def hash(self, adapter: ProductionSystemData) -> str:
        """
        Returns a unique hash for the source considering its location, product type, time model, routing heuristic and output queues.

        Args:
            adapter (ProductionSystemAdapter): Adapter of the production system.

        Raises:
            ValueError: If the product, time model or port is not found in the adapter.

        Returns:
            str: Hash of the source.
        """
        locatable_hash = Locatable.hash(self)
        for product in adapter.product_data:
            if product.type == self.product_type:
                product_hash = product.hash(adapter)
                break
        else:
            raise ValueError(
                f"Product with ID {self.product_type} not found for source {self.ID}."
            )

        for time_model in adapter.time_model_data:
            if time_model.ID == self.time_model_id:
                time_model_hash = time_model.hash()
                break
        else:
            raise ValueError(
                f"Time model with ID {self.time_model_id} not found for source {self.ID}."
            )

        output_queue_hashes = []
        for output_queue in self.ports:
            for queue in adapter.queue_data:
                if queue.ID == output_queue:
                    output_queue_hashes.append(queue.hash())
                    break
            else:
                raise ValueError(
                    f"Queue with ID {output_queue} not found for source {self.ID}."
                )

        return md5(
            (
                "".join(
                    [
                        locatable_hash,
                        product_hash,
                        time_model_hash,
                        self.routing_heuristic,
                        *sorted(output_queue_hashes),
                    ]
                )
            ).encode("utf-8")
        ).hexdigest()

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ID": "S1",
                    "description": "Source 1",
                    "location": [0.0, 0.0],
                    "product_type": "Product_1",
                    "time_model_id": "function_time_model_4",
                    "router": "SimpleRouter",
                    "routing_heuristic": "shortest_queue",
                    "ports": ["SourceQueue"],
                }
            ]
        }
    )
