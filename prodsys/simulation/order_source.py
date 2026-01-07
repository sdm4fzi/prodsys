from __future__ import annotations

from typing import List, TYPE_CHECKING, Optional, Dict, Generator, Tuple
from collections import defaultdict

import logging

from prodsys.simulation import sim, time_model
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
        schedule: Optional[List] = None,
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
        # Schedule for product ID mapping: (order_id, product_type, index) -> product_id
        self.schedule = schedule
        self.schedule_product_map: Dict[Tuple[str, str, int], str] = {}
        # Track product index per order and product type for schedule mapping
        self.order_product_index: Dict[Tuple[str, str], int] = defaultdict(int)

    def set_product_type_mapping(self, product_type_to_data: Dict[str, product_data.ProductData]):
        """
        Sets the mapping from product type to ProductData.

        Args:
            product_type_to_data (Dict[str, ProductData]): Mapping from product type to ProductData.
        """
        self.product_type_to_data = product_type_to_data
        # Build schedule product map after product type mapping is set
        if self.schedule:
            self._build_schedule_product_map()
    
    def _build_schedule_product_map(self):
        """
        Builds a mapping from (order_id, product_type, index) to product_id from schedule.
        This allows OrderSource to use scheduled product IDs when creating products.
        """
        if not self.schedule:
            logger.debug("OrderSource: No schedule provided, skipping product ID mapping")
            return
        
        logger.info(f"OrderSource: Building schedule product map from {len(self.schedule)} schedule events")
        
        # Group schedule events by order (match by time and product type)
        # Track product index per order and product type
        order_product_counters: Dict[Tuple[str, str], int] = defaultdict(int)
        
        # Track which product_ids have already been matched to orders
        # This handles products with multiple processes (e.g., Product_C with P1 and P2)
        # that appear multiple times in the schedule
        product_id_to_order_map: Dict[str, Tuple[str, str, int]] = {}
        
        # Sort schedule events by time to process in order
        sorted_schedule = sorted(self.schedule, key=lambda e: e.time if hasattr(e, 'time') else 0)
        
        for event in sorted_schedule:
            if event.activity == "start state":
                product_id = event.product
                # Extract product type: Product_A_1 -> Product_A (everything except the last part)
                parts = product_id.split("_")
                product_type = "_".join(parts[:-1]) if len(parts) > 1 else parts[0]
                event_time = event.time
                
                # Check if we've already matched this product_id to an order
                # (for products with multiple processes, the same product_id appears multiple times)
                if product_id in product_id_to_order_map:
                    # Reuse the existing mapping
                    key = product_id_to_order_map[product_id]
                    logger.debug(
                        f"OrderSource: Reusing mapping for {product_id} (time={event_time}, process={event.process}) "
                        f"to existing order mapping {key}"
                    )
                    continue
                
                # Try to match with orders by release time and product type
                matched = False
                for order in self.orders:
                    release_time = order.release_time if order.release_time is not None else order.order_time
                    # Match by time (within 0.1 time units) and product type
                    time_diff = abs(release_time - event_time)
                    if time_diff < 0.1:
                        # Check if this order has this product type
                        for ordered_product in order.ordered_products:
                            if ordered_product.product_type == product_type:
                                # Use order ID, product type, and index within that order+type combination
                                key = (order.ID, product_type, order_product_counters[(order.ID, product_type)])
                                self.schedule_product_map[key] = product_id
                                product_id_to_order_map[product_id] = key
                                order_product_counters[(order.ID, product_type)] += 1
                                logger.info(
                                    f"OrderSource: Mapped schedule product {product_id} (time={event_time}, process={event.process}) to "
                                    f"order {order.ID} (release_time={release_time}), product_type {product_type}, "
                                    f"index {order_product_counters[(order.ID, product_type)] - 1}"
                                )
                                matched = True
                                break
                        if matched:
                            break  # Found matching order, move to next schedule event
                    else:
                        logger.debug(
                            f"OrderSource: Time mismatch for {product_id}: schedule_time={event_time}, "
                            f"order_release_time={release_time}, diff={time_diff}"
                        )
                
                if not matched:
                    logger.warning(
                        f"OrderSource: Could not match schedule event {product_id} (time={event_time}, "
                        f"product_type={product_type}, process={event.process}) to any order. Available orders: "
                        f"{[(o.ID, o.release_time or o.order_time, [op.product_type for op in o.ordered_products]) for o in self.orders]}"
                    )
        
        logger.info(f"OrderSource: Built schedule product map with {len(self.schedule_product_map)} entries")
        if logger.isEnabledFor(logging.DEBUG):
            for key, product_id in list(self.schedule_product_map.items())[:5]:
                logger.debug(f"  Schedule map: {key} -> {product_id}")

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
                for product_index in range(quantity):
                    # Check ConWip again before each product release
                    if self.conwip is not None:
                        while len(self.product_factory.products.values()) >= self.conwip:
                            yield self.env.timeout(0.1)
                    
                    # Get product ID from schedule if available
                    product_id = None
                    if self.schedule_product_map:
                        schedule_key = (order.ID, product_type, product_index)
                        product_id = self.schedule_product_map.get(schedule_key)
                        if product_id:
                            logger.debug(
                                f"OrderSource: Using scheduled product ID {product_id} for "
                                f"order {order.ID}, product_type {product_type}, index {product_index}"
                            )
                        else:
                            logger.debug(
                                f"OrderSource: No schedule mapping found for "
                                f"order {order.ID}, product_type {product_type}, index {product_index}. "
                                f"Available keys: {list(self.schedule_product_map.keys())[:5]}"
                            )
                    
                    # Create product with scheduled ID if available
                    product = self.product_factory.create_product(
                        product_data_obj, self.data.routing_heuristic, product_id=product_id
                    )
                    product.update_location(self)
                    
                    # Put product in output queues
                    for queue in self.ports:
                        yield from queue.put(product.data)
                        product.update_location(queue)
                    
                    # Track product instance in order
                    if order.products is None:
                        order.products = []
                    from prodsys.models.order_data import OrderProductInstance
                    order.products.append(OrderProductInstance(
                        product_type=product_type,
                        product_id=product.data.ID
                    ))
                    
                    # Process the product with order_id
                    self.env.process(self.product_processor.process_product(product, order_ID=order.ID))
                    
                    # Track released products
                    self.released_products[order.ID] += 1

