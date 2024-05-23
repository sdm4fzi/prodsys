from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, Union, List, Tuple, Union

if TYPE_CHECKING:
    from prodsys.simulation import product, process, resources, auxiliary, sink
    from prodsys.simulation.product import Locatable



class Request:
    """
    Class to represents requests of a product for a process to be executed by a resource.

    Args:
        process (process.PROCESS_UNION): The process.
        product (product.Product): The product.
        resource (resources.Resource): The resource.
    """
    def __init__(
        self,
        process: process.PROCESS_UNION,
        product: product.Product,
        resource: resources.Resource
    ):
        self.process = process
        self.product = product
        self.resource = resource


    def set_process(self, process: process.PROCESS_UNION):
        """
        Sets the process of the request.

        Args:
            process (process.PROCESS_UNION): The process.
        """
        self.process = process
        # TODO: maybe do some special handling of compound processes here


    def get_process(self) -> process.PROCESS_UNION:
        """
        Returns the process or the capability process of the request 

        Returns:
            process.PROCESS_UNION: The process.
        """
        return self.process

    def get_product(self) -> product.Product:
        """
        Returns the product of the request.

        Returns:
            product.Product: The product.
        """
        return self.product

    def get_resource(self) -> resources.Resource:
        """
        Returns the resource of the request.

        Returns:
            resources.Resource: The resource.
        """
        return self.resource


class SinkRequest(Request):
    """
    Class to represents requests of a product for a storage in a sink to be executed by a resource.

    Args:
        Request (_type_): _description_
    """
    def __init__(
        self,
        product: product.Product,
        sink: sink.Sink
    ):
        self.resource = sink
        self.product = product
        self.process = None
    
class AuxiliaryRequest(Request):
    """
    Represents an auxiliary request in the simulation. The request is associated with an auxiliary which needs to be transported

    Attributes:
        process (process.TransportProcess): The transport process associated with the request.
        product (product.Product): The product associated with the request.
        auxiliary (auxiliary.Auxiliary): The auxiliary associated with the request.
    """

    def __init__(
        self,
        process: process.TransportProcess,
        product: product.Product,
    ):
        self.process: process.TransportProcess = process
        self.product: product.Product = product
        self.auxiliary: auxiliary.Auxiliary = None




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
        process: Union[process.TransportProcess, process.LinkTransportProcess],
        product: Union[product.Product, auxiliary.Auxiliary],
        resource: resources.TransportResource,
        origin: product.Locatable,
        target: product.Locatable,
    ):
        self.process: Union[process.TransportProcess, process.LinkTransportProcess] = process
        self.product: product.Product = product
        self.resource: resources.TransportResource = resource
        self.origin: product.Locatable = origin
        self.target: product.Locatable = target

        self.route: Optional[List[Locatable]] = None


    def set_process(self, process: process.PROCESS_UNION):
        """
        Sets the process of the request.

        Args:
            process (process.PROCESS_UNION): The process.
        """
        self.process = process
        # TODO: maybe do some special handling of compound processes here

    def copy_cached_routes(self, request: TransportResquest):
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

    def get_process(self) -> Union[process.TransportProcess, process.LinkTransportProcess]:
        """
        Returns the transport process of the transport request.

        Returns:
            process.TransportProcess: The transport process.
        """
        return self.process

    def get_resource(self) -> resources.TransportResource:
        """
        Returns the transport resource of the transport request.

        Returns:
            resources.TransportResource: The transport resource.
        """
        return self.resource

    def get_origin(self) -> product.Locatable:
        """
        Returns the origin location of the transport request.

        Returns:
            product.Locatable: The origin location.
        """
        return self.origin

    def get_target(self) -> product.Locatable:
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
