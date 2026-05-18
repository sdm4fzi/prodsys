from __future__ import annotations

from enum import Enum
from hashlib import md5
from typing import TYPE_CHECKING, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict

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
    per_lot: bool = True

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
    per_lot: bool = True
    
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
        per_lot (bool, optional): If True, the dependency is needed once per lot. If False, it's needed for every instance in the lot. Defaults to False.

    Returns:
        _type_: _description_
    """

    required_entity: str
    dependency_type: DependencyType = DependencyType.TOOL
    per_lot: bool = True

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
    per_lot: bool = False

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


class LinkLotEntry(BaseModel):
    """One per-link override of the lot size on a :class:`LinkLotDependencyData`.

    Attributes:
        origin (str): Origin node ID of the link (must match the link in the
            attached :class:`LinkTransportProcessData`).
        target (str): Target node ID of the link.
        min_lot_size (int): Minimum number of items the lot handler must
            collect for *this specific link* before dispatching.
        max_lot_size (int): Maximum number of items that may be bundled
            into a single dispatch on this link.
    """

    origin: str
    target: str
    min_lot_size: int = 1
    max_lot_size: int = 1

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "origin": "StationA",
                    "target": "StationB",
                    "min_lot_size": 1,
                    "max_lot_size": 34,
                }
            ]
        }
    )


class LinkLotDependencyData(LotDependencyData):
    """Lot dependency where the (min, max) lot sizes vary per link.

    The base :class:`LotDependencyData` enforces a *single* (min, max)
    lot size for every dispatch of the process it is attached to.  In
    real shopfloors this is often too coarse — a worker can carry trays
    of up to N products between stations but only ever shuttles a
    single product on the loading-zone shuffle inside one station, even
    though both moves use the same physical worker process.

    :class:`LinkLotDependencyData` lifts that constraint: it inherits
    the base ``min_lot_size`` / ``max_lot_size`` (used as a fallback
    for any link not explicitly listed) and adds a list of
    :class:`LinkLotEntry` overrides.  At request time
    :class:`prodsys.simulation.lot_handler.LotHandler` looks up the
    request's ``(origin, target)`` and, if it finds a matching entry,
    bundles requests using *that* entry's sizes.

    Args:
        ID (str): Dependency ID.
        description (str): Description.
        min_lot_size (int): Default minimum lot size for unmapped links.
        max_lot_size (int): Default maximum lot size for unmapped links.
        link_lot_sizes (List[LinkLotEntry]): Per-link overrides.

    Examples:
        Tray of up to 34 products between stations, single piece
        on intra-station shuffles::

            LinkLotDependencyData(
                ID="dep_lot_worker",
                description="Worker tray bundling per link",
                min_lot_size=1,
                max_lot_size=1,
                link_lot_sizes=[
                    LinkLotEntry(
                        origin="StationA", target="StationB",
                        min_lot_size=1, max_lot_size=34,
                    ),
                    LinkLotEntry(
                        origin="StationA", target="StationA",
                        min_lot_size=1, max_lot_size=1,
                    ),
                ],
            )
    """

    link_lot_sizes: List[LinkLotEntry] = []

    def get_link_lot_sizes(self, origin_id: str, target_id: str) -> Tuple[int, int]:
        """Return ``(min_lot_size, max_lot_size)`` for the given link.

        Falls back to the inherited base values when no entry matches.
        """
        for entry in self.link_lot_sizes:
            if entry.origin == origin_id and entry.target == target_id:
                return entry.min_lot_size, entry.max_lot_size
        return self.min_lot_size, self.max_lot_size

    def hash(self, adapter: ProductionSystemData) -> str:
        base = super().hash(adapter)
        link_repr = "|".join(
            sorted(
                f"{e.origin}->{e.target}:{e.min_lot_size}-{e.max_lot_size}"
                for e in self.link_lot_sizes
            )
        )
        return md5((base + link_repr).encode("utf-8")).hexdigest()


DEPENDENCY_TYPES = Union[
    ProcessDependencyData,
    ResourceDependencyData,
    ToolDependencyData,
    AssemblyDependencyData,
    DisassemblyDependencyData,
    LinkLotDependencyData,
    LotDependencyData,
]