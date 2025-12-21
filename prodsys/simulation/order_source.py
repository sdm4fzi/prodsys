from __future__ import annotations

from typing import List, TYPE_CHECKING, Optional, Dict, Generator
from collections import defaultdict

import logging

from prodsys.simulation import port, sim, time_model
from prodsys.models import source_data, product_data, order_data
from prodsys.simulation.source import Source

if TYPE_CHECKING:
    from prodsys.factories import product_factory

logger = logging.getLogger(__name__)


class OrderSource(Source):
    """
    Class that represents an order source that releases products based on orders.
    Inherits from Source and overrides the product release logic.

    Args:
        env (sim.Environment): The simulation environment.
        data (source_data.OrderSourceData): The order source data.
        product_factory (product_factory.ProductFactory): The product factory.
        orders (List[order_data.OrderData]): List of orders to release.
        conwip (Optional[int]): ConWip limit. Defaults to None.
    """

    def __init__(
        self,
        env: sim.Environment,
        data: source_data.OrderSourceData,
        product_factory: product_factory.ProductFactory,
        orders: List[order_data.OrderData],
        conwip: Optional[int] = None,
    ):
        # Initialize with dummy values for Source base class
        # We'll override the behavior in create_product_loop
        dummy_product_data = product_data.ProductData(
            ID="dummy",
            type="dummy",
            description="",
            processes=[],
            transport_process="",
        )
        from prodsys.models.time_model_data import FunctionTimeModelData
        dummy_time_model = time_model.FunctionTimeModel(
            FunctionTimeModelData(
                ID="dummy",
                description="",
                distribution_function="constant",
                location=0.0,
                scale=0.0,
            ),
        )
        
        # Call parent __init__ with dummy values
        super().__init__(
            env=env,
            data=data,
            product_data=dummy_product_data,
            product_factory=product_factory,
            time_model=dummy_time_model,
            conwip=conwip,
            schedule=None,
        )
        
        # OrderSource-specific attributes
        self.orders = orders
        # Sort orders by release_time (or order_time if release_time is None)
        self.orders.sort(key=lambda o: o.release_time if o.release_time is not None else o.order_time)
        # Track which products from which orders have been released
        self.released_products: Dict[str, int] = defaultdict(int)  # order_id -> count of released products
        # Map product types to their ProductData
        self.product_type_to_data: Dict[str, product_data.ProductData] = {}

    def set_product_type_mapping(self, product_type_to_data: Dict[str, product_data.ProductData]):
        """
        Sets the mapping from product type to ProductData.

        Args:
            product_type_to_data (Dict[str, ProductData]): Mapping from product type to ProductData.
        """
        self.product_type_to_data = product_type_to_data

    def create_product_loop(self) -> Generator:
        """
        Simpy process that creates products from orders based on their release times.
        Overrides the base Source.create_product_loop() method.

        Yields:
            Generator: Yields when products are created or when products are put in output queues.
        """
        # Process orders in chronological order
        for order in self.orders:
            release_time = order.release_time if order.release_time is not None else order.order_time
            
            # Wait until release time
            if release_time > self.env.now:
                yield self.env.timeout(release_time - self.env.now)
            
            # Check ConWip before releasing products from this order
            if self.conwip is not None:
                # Wait until ConWip allows release
                while len(self.product_factory.products.values()) >= self.conwip:
                    yield self.env.timeout(0.1)  # Small timeout to avoid busy waiting
            
            # Release all products from this order
            for ordered_product in order.ordered_products:
                product_type = ordered_product.product_type
                quantity = ordered_product.quantity
                
                # Get ProductData for this product type
                if product_type not in self.product_type_to_data:
                    logger.warning(
                        f"Product type {product_type} not found in product type mapping for order {order.ID}"
                    )
                    continue
                
                product_data_obj = self.product_type_to_data[product_type]
                
                # Release the specified quantity of products
                for _ in range(quantity):
                    # Check ConWip again before each product release
                    if self.conwip is not None:
                        while len(self.product_factory.products.values()) >= self.conwip:
                            yield self.env.timeout(0.1)
                    
                    # Create product
                    product = self.product_factory.create_product(
                        product_data_obj, self.data.routing_heuristic
                    )
                    product.update_location(self)
                    
                    # Put product in output queues
                    for queue in self.ports:
                        yield from queue.put(product.data)
                        product.update_location(queue)
                    
                    # Process the product
                    self.env.process(self.product_processor.process_product(product))
                    
                    # Track released products
                    self.released_products[order.ID] += 1

