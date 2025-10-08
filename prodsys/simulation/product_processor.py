from typing import Generator


from prodsys.simulation import sim
from prodsys.simulation.entities.product import Product





class ProductProcessor:
    """
    Coordinator for products.
    """
    def __init__(self, env: sim.Environment):
        self.env = env

    def process_product(self, product: Product) -> Generator[None, None, None]:
        """
        Processes the product object in a simpy process. The product object is processed after creation until all required production processes are performed and it reaches a sink.
        """
        product.info.log_create_product(
            resource=product.current_locatable, _product=product, event_time=self.env.now
        )
        processing_request = product.router.request_processing(product)
        yield processing_request.completed
        product.info.log_finish_product(
            resource=product.current_locatable, _product=product, event_time=self.env.now
        )
        processing_request.target.register_finished_product(product)
