from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prodsys.simulation import product, process, resources


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
        resource: resources.Resource,
    ):
        self.process = process
        self.product = product
        self.resource = resource

    def get_process(self) -> process.PROCESS_UNION:
        """
        Returns the process or the capability process of the request 

        Returns:
            process.PROCESS_UNION: The process.
        """
        if isinstance(self.process, process.CapabilityProcess):
            for process in self.resource.processes:
                if process.process_data.capability == self.process.process_data.capability:
                    self.process = process

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
        process: process.TransportProcess,
        product: product.Product,
        resource: resources.TransportResource,
        origin: product.Location,
        target: product.Location,
    ):
        self.process: process.TransportProcess = process
        self.product: product.Product = product
        self.resource: resources.TransportResource = resource
        self.origin: product.Location = origin
        self.target: product.Location = target

    def get_process(self) -> process.TransportProcess:
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

    def get_origin(self) -> product.Location:
        """
        Returns the origin location of the transport request.

        Returns:
            product.Location: The origin location.
        """
        return self.origin

    def get_target(self) -> product.Location:
        """
        Returns the target location of the transport request.

        Returns:
            product.Location: The target location.
        """
        return self.target
