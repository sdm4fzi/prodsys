from __future__ import annotations

from typing import Literal, Optional, Union, List
from uuid import uuid1
from pydantic import Field
from pydantic.dataclasses import dataclass

from prodsys.express import core
from prodsys.models.dependency_data import PrimitiveDependencyData, ProcessDependencyData, ResourceDependencyData, LotDependencyData
from prodsys.express.node import Node


@dataclass
class Dependency(core.ExpressObject):
    """
    Abstract base class to represent a dependency.
    """

@dataclass
class ResourceDependency(Dependency):
    required_resource: Resource
    interaction_node: Optional[Node]
    position_type: Literal["relative", "absolute"] = "absolute"
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def to_model(self):
        return ResourceDependencyData(
            ID=self.ID,
            description="",
            required_resource=self.required_resource.ID,
            interaction_node=self.interaction_node.ID if self.interaction_node else None,
            position_type=self.position_type,
        )


@dataclass
class ProcessDependency(Dependency):
    required_process: PROCESS_UNION
    interaction_node: Optional[Node]
    position_type: Literal["relative", "absolute"] = "absolute"
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def to_model(self):
        return ProcessDependencyData(
            ID=self.ID,
            description="",
            required_process=self.required_process.ID,
            interaction_node=self.interaction_node.ID if self.interaction_node else None,
            position_type=self.position_type,
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


@dataclass
class LotDependency(Dependency):
    min_lot_size: int
    max_lot_size: int
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def to_model(self):
        return LotDependencyData(
            ID=self.ID,
            description="",
            min_lot_size=self.min_lot_size,
            max_lot_size=self.max_lot_size,
        )

from prodsys.express.primitive import Primitive
from prodsys.express.process import PROCESS_UNION, Process
from prodsys.express.product import Product
from prodsys.express.resources import Resource
