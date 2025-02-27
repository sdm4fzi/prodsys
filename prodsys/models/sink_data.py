from __future__ import annotations
from hashlib import md5
from typing import List, TYPE_CHECKING
from pydantic import ConfigDict

from prodsys.models.core_asset import CoreAsset, Locatable

if TYPE_CHECKING:
    from prodsys.adapters.adapter import ProductionSystemAdapter


class SinkData(CoreAsset, Locatable):
    """
    Class that represents a sink.

    Args:
        ID (str): ID of the sink.
        description (str): Description of the sink.
        location (List[float]): Location of the sink. It has to be a list of length 2.
        product_type (str): Product type of the sink.
        input_queues (Optional[List[str]], optional): List of input queues of the sink. Defaults to None.

    Examples:
        A sink with ID "SK1":
        ``` py
        import prodsys
        prodsys.sink_data.SinkData(
            ID="SK1",
            description="Sink 1",
            location=[50.0, 50.0],
            product_type="Product_1",
            input_queues=["SinkQueue"],
        )
        ```
    """

    product_type: str
    input_queues: List[str] = []

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ID": "SK1",
                    "description": "Sink 1",
                    "input_location": [50.0, 50.0],
                    "product_type": "Product_1",
                    "input_queues": ["SinkQueue"],
                }
            ]
        }
    )

    def hash(self, adapter: ProductionSystemAdapter) -> str:
        """
        Returns a unique hash for the sink considering its location, product type and input queues.

        Args:
            adapter (ProductionSystemAdapter): Adapter of the production system.

        Raises:
            ValueError: If the product or input queue is not found in the adapter.

        Returns:
            str: Hash of the sink.
        """
        base_class_hash = Locatable.hash(self)
        for product in adapter.product_data:
            if product.product_type == self.product_type:
                product_hash = product.hash(adapter)
                break
        else:
            raise ValueError(
                f"Product with ID {self.product_type} not found for sink {self.ID}."
            )

        input_queue_hashes = []
        for queue_id in self.input_queues:
            for queue in adapter.queue_data:
                if queue.ID == queue_id:
                    input_queue_hashes.append(queue.hash())
                    break
            else:
                raise ValueError(
                    f"Queue with ID {queue_id} not found for sink {self.ID}."
                )

        return md5(
            "".join(
                [base_class_hash, product_hash, *sorted(input_queue_hashes)]
            ).encode("utf-8")
        ).hexdigest()
