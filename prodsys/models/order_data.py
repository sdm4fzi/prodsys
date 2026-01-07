from typing import List, Optional

from pydantic import BaseModel

class OrderedProductData(BaseModel):
    product_type: str
    quantity: int

class OrderProductInstance(BaseModel):
    product_type: str
    product_id: str


class OrderData(BaseModel):
    """
    Class that represents an order data.

    Args:
        ID (str): ID of the order.
        ordered_products (List[OrderedProductData]): Ordered products of the order.
        order_time (float): Time of the order.
        due_time (Optional[float]): Due time of the order. Defaults to None.
        release_time (Optional[float]): Release time of the order. Defaults to None. If not specified, orders are released at the order time.
        priority (int): Priority of the order.
        products (Optional[List[OrderProductInstance]]): Products of the order. Defaults to None.
    """
    ID: str
    ordered_products: List[OrderedProductData]
    order_time: float
    due_time: Optional[float] = None
    release_time: Optional[float] = None
    priority: int
    products: Optional[List[OrderProductInstance]] = None
    