from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prodsys.simulation import product, process, resources


class Request:
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
        return self.process

    def get_product(self) -> product.Product:
        return self.product

    def get_resource(self) -> resources.Resource:
        return self.resource


class TransportResquest(Request):
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
        return self.process

    def get_resource(self) -> resources.TransportResource:
        return self.resource

    def get_origin(self) -> product.Location:
        return self.origin

    def get_target(self) -> product.Location:
        return self.target
