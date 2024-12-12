from uuid import uuid1
from pydantic.dataclasses import dataclass
from typing import List, Optional, Union
from pydantic import Field
from prodsys.express import core, process
from prodsys.express.queue import Store
from prodsys.models import auxiliary_data


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
            quantity_in_storages (List[int]): List of initial quantities in the storages.
            ID (Optional[str], optional): The ID of the auxiliary object. Defaults to a generated UUID.
    """

    relevant_processes: List[
        Union[process.ProductionProcess, process.CapabilityProcess]
    ]
    relevant_transport_processes: List[process.TransportProcess]
    transport_process: process.TransportProcess
    storages: List[Store]
    quantity_in_storages: List[int]
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
            quantity_in_storages=[
                initial_quantity_in_store
                for initial_quantity_in_store in self.quantity_in_storages
            ],
            relevant_processes=[process.ID for process in self.relevant_processes],
            relevant_transport_processes=[
                transportprocess.ID
                for transportprocess in self.relevant_transport_processes
            ],
        )
