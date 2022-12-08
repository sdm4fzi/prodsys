from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Union

import simpy

if TYPE_CHECKING:
    from . import material, process, resources


@dataclass
class Request:
    _process: process.PROCESS_UNION
    _material: material.Material
    _resource: resources.Resourcex

    def get_process(self) -> process.PROCESS_UNION:
        return self._process

    def get_material(self) -> material.Material:
        return self._material
    
    def get_resource(self) -> resources.Resourcex:
        return self._resource

@dataclass
class TransportResquest(Request):
    _process: process.TransportProcess
    _resource: resources.TransportResource

    origin: resources.Resourcex
    target: resources.Resourcex

    def get_process(self) -> process.TransportProcess:
        return self._process
    
    def get_resource(self) -> resources.TransportResource:
        return self._resource

    def get_origin(self) -> resources.Resourcex:
        return self.origin

    def get_target(self) -> resources.Resourcex:
        return self.target