from typing import List, Optional

from pydantic import BaseModel

from prodsys.models.product_data import ProductData

class OrderedProductData(BaseModel):
    product_type: str
    quantity: int


class OrderData(BaseModel):
    ID: str
    ordered_products: List[OrderedProductData]
    order_time: float
    due_time: Optional[float] = None
    release_time: Optional[float] = None
    priority: int
    products: Optional[List[ProductData]] = None
    