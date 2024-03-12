
from typing import TYPE_CHECKING, Generator, List
from pydantic import BaseModel, Field, parse_obj_as
from prodsys.adapters import adapter
from prodsys.factories import process_factory, queue_factory
from prodsys.models import queue_data

from prodsys.simulation import sim
from prodsys.simulation import auxiliary

if TYPE_CHECKING:
        from prodsys.simulation import router
        from prodsys.factories import resource_factory, sink_factory


class AuxiliaryFactory(BaseModel):

        env: sim.Environment
        process_factory: process_factory.ProcessFactory
        storage_factory: queue_factory.StorageFactory
        auxiliaries: List[auxiliary.Auxiliary] = []
        class Config:
                arbitrary_types_allowed = True

        def create_auxiliary(self, adapter: adapter.ProductionSystemAdapter):
                for auxiliary_data in adapter.auxiliary_data:
                        for i, storage in enumerate(auxiliary_data.initial_quantity_in_stores):
                                stor = auxiliary_data.storages[i]
                                storr = next((storage for storage in adapter.storage_data if storage.ID == stor), None)
                                for _ in range(storage):
                                        self.add_auxiliary(auxiliary_data, storr)


        def add_auxiliary(self, auxiliary_data: auxiliary.Auxiliary, storage: queue_data.StorageData):
                values = {}
                values.update({"env": self.env, "auxiliary_data": auxiliary_data})
                transport_process = self.process_factory.get_process(auxiliary_data.transport_process)
                values.update({"transport_process": transport_process})
                storage = self.storage_factory.get_storage(storage.ID)
                values.update({"storage": storage})
                #values.update({"auxiliary_router": None})
                auxiliary_object = parse_obj_as(auxiliary.Auxiliary, values)
                self.auxiliaries.append(auxiliary_object)


        def get_auxiliary(self, ID: str) -> auxiliary.Auxiliary:

                return [s for s in self.auxiliaries if s.auxiliary_data.ID == ID].pop()

# from prodsys.factories import resource_factory, sink_factory
# AuxiliaryFactory.update_forward_refs()