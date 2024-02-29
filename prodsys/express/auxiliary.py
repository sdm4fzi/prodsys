from uuid import uuid1
from pydantic.dataclasses import dataclass
from typing import List, Optional, Union
from pydantic import Field, conlist
from prodsys.express import core, process
from prodsys.models import auxiliary_data, queue_data
import prodsys

@dataclass
class Storage(core.ExpressObject):
        location: conlist(float, min_items=2, max_items=2) # type: ignore
        ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))
       
        capacity: Union[int, float] = 0

        def to_model(self) -> queue_data.StorageData:

                return queue_data.StorageData(
                        ID=self.ID,
                        description="",
                        capacity=self.capacity,
                        location=self.location,
                )

@dataclass
class Auxiliary(core.ExpressObject):

        relevant_processes: List[Union[process.ProductionProcess, process.CapabilityProcess]]
        relevant_transport_processes: List[process.TransportProcess]
        transport_process: process.TransportProcess
        storages: List[Storage]
        initial_quantity_in_stores: List[int]
        ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))
        #router !?
        

        def to_model(self) -> auxiliary_data.AuxiliaryData:

                return auxiliary_data.AuxiliaryData(
                        ID=self.ID,
                        description="",
                        transport_process=self.transport_process.ID,
                        storages= [storage.ID for storage in self.storages],
                        initial_quantity_in_stores=[initial_quantity_in_store for initial_quantity_in_store in self.initial_quantity_in_stores],
                        relevant_processes=[process.ID for process in self.relevant_processes],
                        relevant_transport_processes=[transportprocess.ID for transportprocess in self.relevant_transport_processes]
                )



        
