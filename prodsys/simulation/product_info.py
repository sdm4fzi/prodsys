from prodsys.simulation.entities.product import Product

from prodsys.simulation.state import StateTypeEnum, StateEnum
from prodsys.simulation.locatable import Locatable



class ProductInfo:
    """
    Class that represents information of the current state of a product.

    Args:
        resource_ID (str): ID of the resource that the product is currently at.
        state_ID (str): ID of the state that the product is currently at.
        event_time (float): Time of the event.
        activity (state.StateEnum): Activity of the product.
        product_ID (str): ID of the product.
        state_type (state.StateTypeEnum): Type of the state.
    """

    def __init__(
        self,
        resource_ID: str = None,
        state_ID: str = None,
        event_time: float = None,
        activity: StateEnum = None,
        product_ID: str = None,
        state_type: StateTypeEnum = None,
    ):
        self.resource_ID = resource_ID
        self.state_ID = state_ID
        self.event_time = event_time
        self.activity = activity
        self.product_ID = product_ID
        self.state_type = state_type

    def log_finish_product(
        self,
        resource: Locatable,
        _product: Product,
        event_time: float,
    ):
        """
        Logs the finish of a product.

        Args:
            resource (Union[resources.Resource, sink.Sink, source.Source]): New resource of the product.
            _product (Product): Product that is finished.
            event_time (float): Time of the event.
        """
        self.resource_ID = resource.data.ID
        self.state_ID = resource.data.ID
        self.event_time = event_time
        self.product_ID = _product.data.ID
        self.activity = StateEnum.finished_product
        self.state_type = StateTypeEnum.sink

    def log_create_product(
        self,
        resource: Locatable,
        _product: Product,
        event_time: float,
    ) -> None:
        """
        Logs the creation of a product.

        Args:
            resource (Union[resources.Resource, sink.Sink, source.Source]): New resource of the product.
            _product (Product): Product that is created.
            event_time (float): Time of the event.
        """
        self.resource_ID = resource.data.ID
        self.state_ID = resource.data.ID
        self.event_time = event_time
        self.product_ID = _product.data.ID
        self.activity = StateEnum.created_product
        self.state_type = StateTypeEnum.source

    def log_bind(
        self,
        resource: Locatable,
        _product: Product,
        event_time: float,
    ) -> None:
        """
        Logs the start of the usage of a product.

        Args:
            resource (resources.Resource): Resource that the product is processed at.
            _product (Product): Product that is processed.
            event_time (float): Time of the event.
        """
        # TODO: implement logging for product dependency usage
        # self.resource_ID = resource.data.ID
        # self.state_ID = resource.data.ID
        # self.event_time = event_time
        # self.product_ID = _product.data.ID
        # self.activity = StateEnum.started_product_usage
        # self.state_type = StateTypeEnum.production
        pass

    def log_release(
        self,
        resource: Locatable,
        _product: Product,
        event_time: float,
    ) -> None:
        """
        Logs the end of the usage of a product.

        Args:
            resource (resources.Resource): Resource that the product is processed at.
            _product (Product): Product that is processed.
            event_time (float): Time of the event.
        """
        # self.resource_ID = resource.data.ID
        # self.state_ID = resource.data.ID
        # self.event_time = event_time
        # self.product_ID = _product.data.ID
        # self.activity = StateEnum.finished_product_usage
        # self.state_type = StateTypeEnum.production
        pass
