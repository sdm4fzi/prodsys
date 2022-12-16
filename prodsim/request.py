from __future__ import annotations

from pydantic import BaseModel
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from prodsim import material, process, resources


class Request(BaseModel):
    process: process.PROCESS_UNION
    material: material.Material
    resource: resources.Resourcex

    def get_process(self) -> process.PROCESS_UNION:
        return self.process

    def get_material(self) -> material.Material:
        return self.material
    
    def get_resource(self) -> resources.Resourcex:
        return self.resource

class TransportResquest(Request):
    process: process.TransportProcess
    resource: resources.TransportResource

    origin: resources.Resourcex
    target: resources.Resourcex

    def get_process(self) -> process.TransportProcess:
        return self.process
    
    def get_resource(self) -> resources.TransportResource:
        return self.resource

    def get_origin(self) -> resources.Resourcex:
        return self.origin

    def get_target(self) -> resources.Resourcex:
        return self.target