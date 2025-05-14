from __future__ import annotations

from typing import Optional, Union
from uuid import uuid1
from pydantic import Field
from pydantic.dataclasses import dataclass

from prodsys.express import core
from prodsys.models.dependency_data import DependencyType, PrimitiveDependencyData, ProcessDependencyData, ResourceDependencyData


@dataclass
class Dependency(core.ExpressObject):
    """
    Abstract base class to represent a dependency.
    """



@dataclass
class ResourceDependency(Dependency):
    required_resource: Resource
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def to_model(self):
        return ResourceDependencyData(
            ID=self.ID,
            description="",
            required_resource=self.required_resource.ID,
        )


@dataclass
class ProcessDependency(Dependency):
    required_process: PROCESS_UNION
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def to_model(self):
        return ProcessDependencyData(
            ID=self.ID,
            description="",
            required_process=self.required_process.ID,
        )


@dataclass
class PrimitiveDependency(Dependency):
    required_primitive: Union[Product, Primitive]
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def to_model(self):
        return PrimitiveDependencyData(
            ID=self.ID,
            description="",
            required_primitive=self.required_primitive.ID,
        )

from prodsys.express.primitive import Primitive
from prodsys.express.process import PROCESS_UNION, Process
from prodsys.express.product import Product
from prodsys.express.resources import Resource
