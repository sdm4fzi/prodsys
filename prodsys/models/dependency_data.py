from __future__ import annotations

from enum import Enum
from hashlib import md5
from typing import TYPE_CHECKING, Union


from prodsys.models.core_asset import CoreAsset

if TYPE_CHECKING:
    from prodsys.models.production_system_data import ProductionSystemData


class DependencyType(str, Enum):
    """
    Enum class that represents the type of dependency between two components.

    - PROCESS: Dependency on a process.
    - RESOURCE: Dependency on a resource.
    - PRIMITIVE: Dependency on a primitive. This covers also StoragePrimitives and Products (due to inheritance).
    """

    PROCESS = "process"
    RESOURCE = "resource"
    PRIMITIVE = "primitive"

class DependencyData(CoreAsset):
    dependency_type: DependencyType


class ProcessDependencyData(DependencyData):
    required_process: str
    dependency_type: DependencyType = DependencyType.PROCESS

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


class PrimitiveDependencyData(DependencyData):
    """
    Class that defines a dependency on a primitive. This could mean, e.g. that a product requires a workpiece carrier to be transported or a tool to be processed. The primitive is not a product itself, but a component that is needed for the production process.

    Args:
        ID (str): ID of the dependency.
        description (str): Description of the dependency.
        required_primitive (str): ID of the required primitive.
        dependency_type (DependencyType, optional): Type of the dependency. Defaults to DependencyType.PRIMITIVE.

    Returns:
        _type_: _description_
    """

    required_primitive: str
    dependency_type: DependencyType = DependencyType.PRIMITIVE

    def hash(self, adapter: ProductionSystemData) -> str:
        """
        Function to hash the primitive dependency.

        Returns:
            str: Hash of the primitive dependency.
        """
        primitive_hash = ""
        for primitive in adapter.primitive_data:
            if primitive.ID == self.required_primitive:
                primitive_hash = primitive.hash(adapter)
        return md5(
            "".join([self.dependency_type, primitive_hash]).encode("utf-8")
        ).hexdigest()


DEPENDENCY_TYPES = Union[
    ProcessDependencyData,
    ResourceDependencyData,
    PrimitiveDependencyData,
]