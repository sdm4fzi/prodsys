from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, Union, List, Tuple, Union


if TYPE_CHECKING:
    from prodsys.simulation.product import Product, Locatable
    from prodsys.simulation.process import (
        PROCESS_UNION,
        TransportProcess,
        LinkTransportProcess,
        CapabilityProcess,
        ProductionProcess
    )
    from prodsys.simulation.resources import Resource, TransportResource
    from prodsys.simulation.sink import Sink
    from prodsys.simulation.auxiliary import Auxiliary
    from prodsys.simulation.store import Store


class Request:
    """
    Class to represents requests of a product for a process to be executed by a resource.

    Args:
        process (process.PROCESS_UNION): The process.
        product (product.Product): The product.
        resource (resources.Resource): The resource.
    """

    def __init__(self, process: PROCESS_UNION, product: Product, resource: Resource):
        self.process = process
        self.product = product
        self.resource = resource

    def set_process(self, process: PROCESS_UNION):
        """
        Sets the process of the request.

        Args:
            process (process.PROCESS_UNION): The process.
        """
        self.process = process
        # TODO: maybe do some special handling of compound processes here

    def get_process(self) -> PROCESS_UNION:
        """
        Returns the process or the capability process of the request

        Returns:
            process.PROCESS_UNION: The process.
        """
        return self.process

    def get_product(self) -> Product:
        """
        Returns the product of the request.

        Returns:
            product.Product: The product.
        """
        return self.product

    def get_resource(self) -> Resource:
        """
        Returns the resource of the request.

        Returns:
            resources.Resource: The resource.
        """
        return self.resource


class ToTransportRequest(Request):
    """
    Class to represents requests of a product for a storage in a queue to be executed by a resource.

    Args:
        Request (_type_): _description_
    """

    def __init__(self, product: Product, target: Store | Resource | Sink):
        self.resource = target
        self.product = product
        self.process = None


class ReworkRequest(Request):
    """
    Class to represents requests of a product for a rework process to be executed by a resource.

    Args:
        Request (_type_): _description_

    Returns:
        _type_: _description_
    """

    def __init__(self, failed_process: ProductionProcess | CapabilityProcess, product: Product):
        self.process = failed_process
        self.product = product
        self.resource = None

class AuxiliaryRequest(Request):
    """
    Represents an auxiliary request in the simulation. The request is associated with an auxiliary which needs to be transported

    Attributes:
        process (process.TransportProcess): The transport process associated with the request.
        product (Optional[product.Product]): The product associated with the request.
        auxiliary (Optional[auxiliary.Auxiliary]): The auxiliary associated with the request.
        resource (Optional[resources.Resource]): The resource associated with the request to be the target of the transport of the auxiliaryand where it is needed.
    """

    def __init__(
        self,
        process: TransportProcess,
        product: Optional[Product] = None,
        auxiliary: Optional[Auxiliary] = None,
        resource: Optional[Resource] = None,
    ):
        self.process: TransportProcess = process
        self.product: Optional[Product] = product
        self.auxiliary: Optional[Auxiliary] = auxiliary
        self.resource: Optional[Resource] = resource

        # TODO: rework this method. It is only used for interface homogenization -> restructure requests to be more general...
        self.origin: Optional[Locatable] = None
        self.target: Optional[Locatable] = None
        self.route: Optional[List[Locatable]] = None

    def set_route(self, route: List[Locatable]):
        """
        Caches a possible route of the transport request used later for setting the resource of the transport request.

        Args:
            process (process.TransportProcess): The process.
            route (List[product.Locatable]): The route.
        """
        # TODO: rework this method. It is only used for interface homogenization -> restructure requests to be more general...
        pass


class TransportResquest(Request):
    """
    Class to represents requests of a product for a transport process to be executed by a transport resource. Additionally, it contains the origin and target locations of the transport.

    Args:
        process (process.TransportProcess): The transport process.
        product (product.Product): The product.
        resource (resources.TransportResource): The transport resource.
        origin (product.Location): The origin location, either a resource, source or sink.
        target (product.Location): The target location, either a resource, source or sink.
    """

    def __init__(
        self,
        process: Union[TransportProcess, LinkTransportProcess],
        product: Union[Product, Auxiliary],
        resource: TransportResource,
        origin: Locatable,
        target: Locatable,
    ):
        self.process: Union[TransportProcess, LinkTransportProcess] = process
        self.product: Product = product
        self.resource: TransportResource = resource
        self.origin: Locatable = origin
        self.target: Locatable = target

        self.route: Optional[List[Locatable]] = None

    def set_process(self, process: PROCESS_UNION):
        """
        Sets the process of the request.

        Args:
            process (process.PROCESS_UNION): The process.
        """
        self.process = process
        # TODO: maybe do some special handling of compound processes here

    def copy_cached_routes(self, request: "TransportResquest"):
        """
        Copies the cached routes from another transport request.

        Args:
            request (TransportResquest): The transport request.
        """
        self.route = request.route

    def set_route(self, route: List[Locatable]):
        """
        Caches a possible route of the transport request used later for setting the resource of the transport request.

        Args:
            process (process.TransportProcess): The process.
            route (List[product.Locatable]): The route.
        """
        self.route = route

    def get_process(self) -> Union[TransportProcess, LinkTransportProcess]:
        """
        Returns the transport process of the transport request.

        Returns:
            process.TransportProcess: The transport process.
        """
        return self.process

    def get_resource(self) -> TransportResource:
        """
        Returns the transport resource of the transport request.

        Returns:
            resources.TransportResource: The transport resource.
        """
        return self.resource

    def get_origin(self) -> Locatable:
        """
        Returns the origin location of the transport request.

        Returns:
            product.Locatable: The origin location.
        """
        return self.origin

    def get_target(self) -> Locatable:
        """
        Returns the target location of the transport request.

        Returns:
            product.Locatable: The target location.
        """
        return self.target

    def get_route(self) -> List[Locatable]:
        """
        Returns the route of the transport request.

        Returns:
            List[product.Locatable]: The route.

        """
        return self.route
