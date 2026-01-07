from __future__ import annotations

from typing import Literal, Optional, Union, List
from uuid import uuid1
from pydantic import Field
from pydantic.dataclasses import dataclass

from prodsys.express import core
from prodsys.models.dependency_data import ToolDependencyData, ProcessDependencyData, ResourceDependencyData, LotDependencyData, AssemblyDependencyData, DisassemblyDependencyData
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
    per_lot: bool = True
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def to_model(self):
        # Infer a resource type hint to support downstream dependency reconciliation.
        resource_type_hint = ""
        try:
            processes = getattr(self.required_resource, "processes", []) or []
            if processes:
                # Import locally to avoid circular imports.
                from prodsys.express import process as _process_module

                if any(
                    isinstance(proc, (_process_module.TransportProcess, _process_module.LinkTransportProcess))
                    for proc in processes
                ):
                    resource_type_hint = "transport_resource"
                else:
                    resource_type_hint = "production_resource"
        except Exception:
            # Fallback to empty hint if inference fails.
            resource_type_hint = ""

        return ResourceDependencyData(
            ID=self.ID,
            description=resource_type_hint,
            required_resource=self.required_resource.ID,
            interaction_node=self.interaction_node.ID if self.interaction_node else None,
            position_type=self.position_type,
            per_lot=self.per_lot,
        )


@dataclass
class ProcessDependency(Dependency):
    required_process: PROCESS_UNION
    interaction_node: Optional[Node]
    position_type: Literal["relative", "absolute"] = "absolute"
    per_lot: bool = True
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def to_model(self):
        return ProcessDependencyData(
            ID=self.ID,
            description="",
            required_process=self.required_process.ID,
            interaction_node=self.interaction_node.ID if self.interaction_node else None,
            position_type=self.position_type,
            per_lot=self.per_lot,
        )


@dataclass
class ToolDependency(Dependency):
    required_entity: Union[Product, Primitive]
    per_lot: bool = False
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def to_model(self):
        return ToolDependencyData(
            ID=self.ID,
            description="",
            required_entity=self.required_entity.ID,
            per_lot=self.per_lot,
        )


@dataclass
class AssemblyDependency(Dependency):
    required_entity: Union[Product, Primitive]
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def to_model(self):
        return AssemblyDependencyData(
            ID=self.ID,
            description="",
            required_entity=self.required_entity.ID,
        )


@dataclass
class DisassemblyDependency(Dependency):
    required_entity: Union[Product, Primitive]
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def to_model(self):
        return DisassemblyDependencyData(
            ID=self.ID,
            description="",
            required_entity=self.required_entity.ID,
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
from prodsys.express.process import PROCESS_UNION
from prodsys.express.product import Product
from prodsys.express.resources import Resource

