from uuid import uuid1
from pydantic.dataclasses import dataclass
from typing import List, Optional, Union
from pydantic import Field, conlist
from prodsys.express import core, process
from prodsys.models import auxiliary_data, queue_data, source_data
import prodsys

@dataclass
class Storage(core.ExpressObject):
        """
        Represents a storage object for auxiliaries. If an auxiliary is not needed it is always transported back to the storage.

        Attributes:
                location (List[float]): The location coordinates of the storage.
                ID (Optional[str]): The unique identifier of the storage.
                capacity (Union[int, float]): The capacity of the storage.
        """

        location: conlist(float, min_items=2, max_items=2) # type: ignore
        ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))
        capacity: Union[int, float] = 0

        def to_model(self) -> queue_data.StorageData:
                """
                Converts the storage object to a `StorageData` model.

                Returns:
                        StorageData: The converted storage data.
                """
                return queue_data.StorageData(
                        ID=self.ID,
                        description="",
                        capacity=self.capacity,
                        location=self.location,
                )

@dataclass
class Auxiliary(core.ExpressObject):
        """
        Represents an auxiliary object in the production system. The auxiliary can be a tool for a station or a pallet or tray for the transport.
        Auxiliaries are stored at storages, which are represented by the `Storage` class. The auxiliary has a minimum quantity at every storage.
        Processes where the auxiliary is needed, are defined.

        Attributes:
                relevant_processes (List[Union[process.ProductionProcess, process.CapabilityProcess]]): List of relevant production or capability processes.
                relevant_transport_processes (List[process.TransportProcess]): List of relevant transport processes.
                transport_process (process.TransportProcess): The transport process associated with the auxiliary object.
                storages (List[Storage]): List of storages associated with the auxiliary object.
                initial_quantity_in_stores (List[int]): List of initial quantities in the storages.
                ID (Optional[str], optional): The ID of the auxiliary object. Defaults to a generated UUID.
        """

        relevant_processes: List[Union[process.ProductionProcess, process.CapabilityProcess]]
        relevant_transport_processes: List[process.TransportProcess]
        transport_process: process.TransportProcess
        storages: List[Storage]
        initial_quantity_in_stores: List[int]
        ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

        def to_model(self) -> auxiliary_data.AuxiliaryData:
                """
                Converts the Auxiliary object to an AuxiliaryData object.

                Returns:
                        auxiliary_data.AuxiliaryData: The converted AuxiliaryData object.
                """
                return auxiliary_data.AuxiliaryData(
                        ID=self.ID,
                        description="",
                        transport_process=self.transport_process.ID,
                        storages=[storage.ID for storage in self.storages],
                        initial_quantity_in_stores=[initial_quantity_in_store for initial_quantity_in_store in self.initial_quantity_in_stores],
                        relevant_processes=[process.ID for process in self.relevant_processes],
                        relevant_transport_processes=[transportprocess.ID for transportprocess in self.relevant_transport_processes]
                )



        
