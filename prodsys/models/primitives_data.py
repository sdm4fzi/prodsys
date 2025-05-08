from __future__ import annotations
from hashlib import md5
from typing import Optional, Union, List, Dict, TYPE_CHECKING
from pydantic import ConfigDict, model_validator
from prodsys.models.core_asset import CoreAsset

if TYPE_CHECKING:
    from prodsys.models.production_system_data import ProductionSystemData


class PrimitiveData(CoreAsset):
    """
    Class that represents a primitive in the production system. A primitive is a component that can be transported and stored. A primitive can be a dependency for processes, but cannot perform any processes itself.


    Examples for a primitive are workpiece carriers, simple assembly components or tools.
    """

    type: str
    transport_process: str


class StoredPrimitive(PrimitiveData):
    """
    Class that represents a stored primitive in the production system. A stored primitive is a primitive that is stored in a storage. A stored primitive can be a dependency for processes, but cannot perform any processes itself.


    Examples for a stored primitive are workpiece carriers, simple assembly components or tools.
    """

    type: str
    transport_process: str
    storages: List[str]
    quantity_in_storages: List[int] = []

    def hash(self, adapter: ProductionSystemData) -> str:
        """
        Returns a unique hash for the stored primitive considering its type, transport process and storages.

        Args:
            adapter (ProductionSystemAdapter): Adapter of the production system.

        Returns:
            str: Hash of the stored primitive.
        """
        return md5(
            "".join([self.type, self.transport_process, str(self.storages)]).encode(
                "utf-8"
            )
        ).hexdigest()
