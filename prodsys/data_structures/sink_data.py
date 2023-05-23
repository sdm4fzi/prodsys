from __future__ import annotations

from typing import Literal, Union, List, Tuple, Optional

from pydantic import validator, conlist

from prodsys.data_structures.core_asset import CoreAsset


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
