from typing import List

from pydantic import BaseModel

from prodsys.models.product_data import ProductData

class OrderedProductData(BaseModel):
    product_type: str
    quantity: int


class OrderData(BaseModel):
    ID: str
    ordered_products: List[OrderedProductData]
    order_time: float
    release_time: float
    due_time: float
    priority: int
    products: List[ProductData]
    