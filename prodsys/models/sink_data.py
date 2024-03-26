from __future__ import annotations
from hashlib import md5
from typing import Literal, Union, List, Tuple, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from prodsys.adapters.adapter import ProductionSystemAdapter
from pydantic import validator, conlist

from prodsys.models.core_asset import CoreAsset


class SinkData(CoreAsset):
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

    location: conlist(float, min_items=2, max_items=2)
    product_type: str
    input_queues: Optional[List[str]]
    
    def tomd5(self, adapter: ProductionSystemAdapter) -> str:
        product_type = self.product_type
        for sink_item in adapter.sink_data:
            for product_item in adapter.product_data:
                if product_item.ID == sink_item.product_type:
                    product_type = product_item.tomd5(adapter)
        return md5("".join([str(item) for item in self.location] + [product_type]).encode("utf-8")).hexdigest()
    
    class Config:
        schema_extra = {
            "example": {
                "summary": "Sink",
                "value": {
                    "ID": "SK1",
                    "description": "Sink 1",
                    "location": [50.0, 50.0],
                    "product_type": "Product_1",
                    "input_queues": ["SinkQueue"],
                },
            }
        }
