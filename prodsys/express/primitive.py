from uuid import uuid1
from pydantic.dataclasses import dataclass
from typing import List, Optional, Union
from pydantic import Field
from prodsys.express import core, process
from prodsys.express.queue import Store
from prodsys.models import dependency_data, primitives_data


@dataclass
class Primitive(core.ExpressObject):
    """
    Class that represents a primitive in the production system. A primitive is a component that can be transported and stored. A primitive can be a dependency for processes, but cannot perform any processes itself.
    Examples for a primitive are workpiece carriers, simple assembly components or tools.

    Args:
        transport_process (process.TransportProcess): Transport process of the primitive.
        storages (List[Store]): List of storages where the primitive can be stored.
        quantity_in_storages (List[int]): List of quantities in each storage.
        ID (str): ID of the primitive.
    """

    transport_process: process.TransportProcess
    storages: List[Store]
    quantity_in_storages: List[int]
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def to_model(self) -> primitives_data.PrimitiveData:
        """
        Converts the Primitive object to an PrimitiveData object.

        Returns:
            primitives_data.PrimitiveData: An instance of the PrimitiveData object.
        """
        return primitives_data.StoredPrimitive(
            ID=self.ID,
            description="",
            type=self.ID,
            transport_process=self.transport_process.ID,
            storages=[storage.ID for storage in self.storages],
            quantity_in_storages=[
                initial_quantity_in_store
                for initial_quantity_in_store in self.quantity_in_storages
            ],
        )
