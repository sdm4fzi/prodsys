from typing import Generator, Optional


from prodsys.simulation import sim
from prodsys.simulation.entities.product import Product



class ProductProcessor:
    """
    Coordinator for products.
    """
    def __init__(self, env: sim.Environment):
        self.env = env

    def process_product(self, product: Product, order_ID: Optional[str] = None) -> Generator[None, None, None]:
        """
        Processes the product object in a simpy process. The product object is processed after creation until all required production processes are performed and it reaches a sink.
        
        Args:
            product (Product): The product to process.
            order_ID (Optional[str]): ID of the order that this product belongs to. Defaults to None.
        """
        product.info.log_create_product(
            resource=product.current_locatable, _product=product, event_time=self.env.now, order_ID=order_ID
        )
        processing_request = product.router.request_processing(product)
        yield processing_request.completed
        product.info.log_finish_product(
            resource=product.current_locatable, _product=product, event_time=self.env.now
        )
        processing_request.target.register_finished_product(product)
