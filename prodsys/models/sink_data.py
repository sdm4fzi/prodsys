from __future__ import annotations
from hashlib import md5
from typing import List, Optional, TYPE_CHECKING
from pydantic import ConfigDict

from prodsys.models.core_asset import CoreAsset, Locatable

if TYPE_CHECKING:
    from prodsys.models.production_system_data import ProductionSystemData


class SinkData(CoreAsset, Locatable):
    """
    Class that represents a sink.

    Args:
        ID (str): ID of the sink.
        description (str): Description of the sink.
        location (List[float]): Location of the sink. It has to be a list of length 2.
        product_type (str): Product type of the sink.
        ports (Optional[List[str]], optional): List of ports of the sink. Defaults to None.

    Examples:
        A sink with ID "SK1":
        ``` py
        import prodsys
        prodsys.sink_data.SinkData(
            ID="SK1",
            description="Sink 1",
            location=[50.0, 50.0],
            product_type="Product_1",
            ports=["SinkQueue"],
        )
        ```
    """

    product_type: str
    ports: Optional[List[str]] = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ID": "SK1",
                    "description": "Sink 1",
                    "location": [50.0, 50.0],
                    "product_type": "Product_1",
                    "ports": ["SinkQueue"],
                }
            ]
        }
    )

    def hash(self, adapter: ProductionSystemData) -> str:
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
            if product.type == self.product_type:
                product_hash = product.hash(adapter)
                break
        else:
            raise ValueError(
                f"Product with ID {self.product_type} not found for sink {self.ID}."
            )

        port_hashes = []
        if self.ports:
            for port_id in self.ports:
                for port in adapter.port_data:
                    if port.ID == port_id:
                        port_hashes.append(port.hash())
                        break
                else:
                    raise ValueError(
                        f"Queue with ID {port_id} not found for sink {self.ID}."
                    )

        return md5(
            "".join([base_class_hash, product_hash, *sorted(port_hashes)]).encode(
                "utf-8"
            )
        ).hexdigest()
