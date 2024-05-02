from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List, Tuple, Union

if TYPE_CHECKING:
    from prodsys.simulation import product, process, resources
    from prodsys.simulation.product import Location



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
    ):
        self.process = process
        self.product = product
        self.resource: Optional[resources.Resource] = None

    def set_resource(self, resource: resources.Resource):
        """
        Sets the resource of the request.

        Args:
            resource (resources.Resource): The resource.
        """
        self.resource = resource
        for process in self.resource.processes:
            if process.matches_request(self):
                # TODO: check whether this needs adaption for compound processes...
                self.process = process

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
        product: product.Product,
        origin: product.Location,
        target: product.Location
    ):
        self.process: Union[process.TransportProcess, process.LinkTransportProcess] = process
        self.product: product.Product = product
        self.resource: resources.TransportResource = None
        self.origin: product.Location = origin
        self.target: product.Location = target

        self.possible_paths: List[Tuple[process.LinkTransportProcess, List[Location]]] = []
        self.path: Optional[List[Location]] = None

    def cache_possible_path_of_process(self, process: process.TransportProcess, path: List[Location]):
        """
        Caches a possible path of the transport request used later for setting the resource of the transport request.

        Args:
            process (process.TransportProcess): The process.
            path (List[product.Location]): The path.
        """
        self.possible_paths.append((process, path))

    def set_resource(self, resource: resources.Resource):
        """
        Sets the resource of the transport request. Also sets the path of the transport request and upadtes the transport process to the one used by the resource for executing the request.
        
        Args:
            resource (resources.TransportResource): The resource.
        """
        if not self.possible_paths:
            raise ValueError("No possible paths have been set. Resource should not be set before possible paths exist.")
        possible_paths_of_routed_resource = []
        for process, path in self.possible_paths:
            if any(resource_process.process_data.ID == process.process_data.ID for resource_process in resource.processes):
                possible_paths_of_routed_resource.append((process, path))
        if not possible_paths_of_routed_resource:
            raise ValueError("The resource does not have any processes that can perform the possible paths from the routing.")
        if len(possible_paths_of_routed_resource) > 1:
            raise ValueError("The resource has multiple processes that can perform the possible paths from the routing. This is not allowed, since distinct association is not possible.")
        
        self.path = possible_paths_of_routed_resource[0][1]
        self.process = possible_paths_of_routed_resource[0][0]
        self.resource = resource

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
    
    def get_path(self) -> List[Location]:
        """
        Returns the path of the transport request.

        Returns:
            List[product.Location]: The path.

        """
        return self.path
