
from typing import List
from pydantic import BaseModel
from prodsys.adapters import adapter
from prodsys.factories import process_factory, queue_factory

from prodsys.simulation import sim


class AuxiliaryFactory(BaseModel):

        env: sim.Environment
        #auxiliaries: List[auxiliary.Auxiliary] = []
        transport_process: process_factory.ProcessFactory
        storages: List[queue_factory.StorageFactory]
        initial_quantity_in_stores: List[int] = []
        relevant_processes: List[process_factory.ProcessFactory]
        relevant_processes: List[process_factory.ProcessFactory]

        def create_auxiliary(self, adapter: adapter.ProductionSystemAdapter):
                for auxiliary_data in adapter.auxiliary_data:
                        values = {}
                        values.update({"env": self.env, "storage_data": auxiliary_data})




from prodsys.simulation import auxiliary
auxiliary.Auxiliary.update_forward_refs()