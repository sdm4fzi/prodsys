from __future__ import annotations

from enum import Enum
from hashlib import md5
from typing import TYPE_CHECKING, Literal, Optional, Union


from prodsys.models.core_asset import CoreAsset

if TYPE_CHECKING:
    from prodsys.models.production_system_data import ProductionSystemData


class DependencyType(str, Enum):
    """
    Enum class that represents the type of dependency between two components.

    - PROCESS: Dependency on a process.
    - RESOURCE: Dependency on a resource.
    - TOOL: Dependency on a tool. For example, a tool needed for a production process (e.g. a drill bit) or a work piece carrier for a transport process.
    - ASSEMBLY: Dependency on an assembly. A primitive or product needed for an assembly process.
    - DISASSEMBLY: Dependency on a disassembly. A primitive or product created by an disassembly process.
    - LOT: Dependency on a lot. For example, a lot needed for a production process (e.g. a lot of screws) or a work piece carrier for a transport process.
    """
    PROCESS = "process"
    RESOURCE = "resource"
    TOOL = "tool"
    ASSEMBLY = "assembly"
    DISASSEMBLY = "disassembly"
    LOT = "lot"

class DependencyData(CoreAsset):
    dependency_type: DependencyType


class ProcessDependencyData(DependencyData):
    required_process: str
    dependency_type: DependencyType = DependencyType.PROCESS
    interaction_node: Optional[str] = None
    position_type: Literal["relative", "absolute"] = "absolute"

    def hash(self, adapter: ProductionSystemData) -> str:
        """
        Function to hash the process dependency.

        Returns:
            str: Hash of the process dependency.
        """
        process_hash = ""
        for process in adapter.process_data:
            if process.ID == self.required_process:
                process_hash = process.hash(adapter)
        return md5(
            "".join([self.dependency_type, process_hash]).encode("utf-8")
        ).hexdigest()


class ResourceDependencyData(DependencyData):
    required_resource: str
    dependency_type: DependencyType = DependencyType.RESOURCE
    interaction_node: Optional[str] = None
    position_type: Literal["relative", "absolute"] = "absolute"

    def hash(self, adapter: ProductionSystemData) -> str:
        """
        Function to hash the resource dependency.

        Returns:
            str: Hash of the resource dependency.
        """
        resource_hash = ""
        for resource in adapter.resource_data:
            if resource.ID == self.required_resource:
                resource_hash = resource.hash(adapter)
        return md5(
            "".join([self.dependency_type, resource_hash]).encode("utf-8")
        ).hexdigest()


class ToolDependencyData(DependencyData):
    """
    Class that defines a dependency on a tool. This could mean, e.g. that a product requires a workpiece carrier to be transported or a tool to be processed. The tool is not a product itself, but a component that is needed for the production process.

    Args:
        ID (str): ID of the dependency.
        description (str): Description of the dependency.
        required_primitive (str): ID of the required primitive.
        dependency_type (DependencyType, optional): Type of the dependency. Defaults to DependencyType.PRIMITIVE.

    Returns:
        _type_: _description_
    """

    required_entity: str
    dependency_type: DependencyType = DependencyType.TOOL

    def hash(self, adapter: ProductionSystemData) -> str:
        """
        Function to hash the primitive dependency.

        Returns:
            str: Hash of the primitive dependency.
        """
        entity_hash = ""
        for entity in adapter.primitive_data + adapter.product_data:
            if entity.ID == self.required_entity:
                entity_hash = entity.hash(adapter)
        return md5(
            "".join([self.dependency_type, entity_hash]).encode("utf-8")
        ).hexdigest()


class AssemblyDependencyData(DependencyData):
    required_entity: str
    dependency_type: DependencyType = DependencyType.ASSEMBLY

    def hash(self, adapter: ProductionSystemData) -> str:
        """
        Function to hash the assembly dependency.

        Returns:
            str: Hash of the assembly dependency.
        """
        entity_hash = ""
        for entity in adapter.primitive_data + adapter.product_data:
            if entity.ID == self.required_entity:
                entity_hash = entity.hash(adapter)
        return md5(
            "".join([self.dependency_type, entity_hash]).encode("utf-8")
        ).hexdigest()


class DisassemblyDependencyData(DependencyData):
    required_entity: str
    dependency_type: DependencyType = DependencyType.DISASSEMBLY

    def hash(self, adapter: ProductionSystemData) -> str:
        """
        Function to hash the disassembly dependency.

        Returns:
            str: Hash of the disassembly dependency.
        """
        entity_hash = ""
        for entity in adapter.primitive_data + adapter.product_data:
            if entity.ID == self.required_entity:
                entity_hash = entity.hash(adapter)
        return md5(
            "".join([self.dependency_type, entity_hash]).encode("utf-8")
        ).hexdigest()


class LotDependencyData(DependencyData):
    """
    Class that defines that processes need to be performed with a carrier, specifying also how many (max / min) products should be placed on this carrier
    """
    min_lot_size: int = 1
    max_lot_size: int = 1
    input_output: Literal["input", "output", "input_output"] = "input_output"
    dependency_type: DependencyType = DependencyType.LOT

    def hash(self, adapter: ProductionSystemData) -> str:
        """
        Function to hash the lot dependency.

        Returns:
            str: Hash of the lot dependency.
        """
        return md5(
            "".join([str(self.dependency_type.value), str(self.min_lot_size), str(self.max_lot_size), str(self.input_output)]).encode("utf-8")
        ).hexdigest()


DEPENDENCY_TYPES = Union[
    ProcessDependencyData,
    ResourceDependencyData,
    ToolDependencyData,
    AssemblyDependencyData,
    DisassemblyDependencyData,
    LotDependencyData,
]