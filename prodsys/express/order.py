from __future__ import annotations

from typing import List, Optional
from uuid import uuid1

from pydantic import Field
from pydantic.dataclasses import dataclass

from prodsys.express import core
from prodsys.express.product import Product
from prodsys.models import order_data


@dataclass
class OrderedProduct(core.ExpressObject):
    """
    Class that represents an ordered product in an order.

    Args:
        product (Product): The product to order.
        quantity (int): Quantity of the product to order.
    """

    product: Product
    quantity: int

    def to_model(self) -> order_data.OrderedProductData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            order_data.OrderedProductData: An instance of the data object.
        """
        return order_data.OrderedProductData(
            product_type=self.product.ID,
            quantity=self.quantity,
        )


@dataclass
class Order(core.ExpressObject):
    """
    Class that represents an order.

    Args:
        ordered_products (List[OrderedProduct]): List of products to order.
        order_time (float): Time when the order was placed.
        release_time (Optional[float]): Time when the order should be released. If not specified, uses order_time.
        priority (int): Priority of the order.
        ID (str): ID of the order.
    """

    ordered_products: List[OrderedProduct]
    order_time: float
    release_time: Optional[float] = None
    priority: int = 1
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def to_model(self) -> order_data.OrderData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            order_data.OrderData: An instance of the data object.
        """
        return order_data.OrderData(
            ID=self.ID,
            ordered_products=[op.to_model() for op in self.ordered_products],
            order_time=self.order_time,
            release_time=self.release_time,
            priority=self.priority,
        )

