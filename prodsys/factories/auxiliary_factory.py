
from typing import TYPE_CHECKING, Generator, List
from pydantic import BaseModel, Field, parse_obj_as
from prodsys.adapters import adapter
from prodsys.factories import process_factory, queue_factory, resource_factory, sink_factory
from prodsys.models import queue_data, auxiliary_data

from prodsys.simulation import sim, router
from prodsys.simulation import auxiliary, logger


from prodsys.models import source_data
class AuxiliaryFactory(BaseModel):

        env: sim.Environment
        process_factory: process_factory.ProcessFactory
        storage_factory: queue_factory.StorageFactory
        resource_factory: resource_factory.ResourceFactory
        sink_factory: sink_factory.SinkFactory
        auxiliaries: List[auxiliary.Auxiliary] = []
        event_logger: logger.EventLogger = Field(default=False, init=False)
        auxiliary_counter = 0
        class Config:
                arbitrary_types_allowed = True

        def create_auxiliary(self, adapter: adapter.ProductionSystemAdapter):
                #TODO: Add logger
                for auxiliary_data in adapter.auxiliary_data:
                        for i, storage in enumerate(auxiliary_data.initial_quantity_in_stores):
                                stor = auxiliary_data.storages[i]
                                storr = next((storage for storage in adapter.storage_data if storage.ID == stor), None)
                                for _ in range(storage):
                                        auxiliary = self.add_auxiliary(auxiliary_data, storr)
                                        #logger.debug({"ID": auxiliary.data.ID, "sim_time": self.env.now, "resource": self.data.ID, "product": auxilairy.data.ID, "event": f"Created auxiliary"})



        def add_auxiliary(self, auxiliary_data: auxiliary_data.AuxiliaryData, storage: queue_data.StorageData):
                values = {}
                auxiliary_data = auxiliary_data.copy()
                auxiliary_data.ID = ( str(auxiliary_data.auxiliary_type) + "_" + str(self.auxiliary_counter))
                values.update({"env": self.env, "data": auxiliary_data})
                transport_process = self.process_factory.get_process(auxiliary_data.transport_process)
                values.update({"transport_process": transport_process})
                storage = self.storage_factory.get_storage(storage.ID)
                values.update({"storage": storage})
                router = self.get_router(source_data.RoutingHeuristic.random) # Add the routing_heuristic in auxiliary_data, like in source_data
                auxiliary_object = parse_obj_as(auxiliary.Auxiliary, values)
                auxiliary_object.auxiliary_router = router
                auxiliary_object.current_location = storage

                if self.event_logger:
                        self.event_logger.observe_terminal_auxiliary_states(auxiliary_object)

                self.auxiliary_counter += 1
                self.auxiliaries.append(auxiliary_object)
                return auxiliary_object


        def get_auxiliary(self, ID: str) -> auxiliary.Auxiliary:

                return [s for s in self.auxiliaries if s.data.ID == ID].pop()
                

        def get_router(self, routing_heuristic: str):
                return router.Router(
                self.resource_factory,
                self.sink_factory,
                self,
                router.ROUTING_HEURISTIC[routing_heuristic],
                )
        

# from prodsys.factories import resource_factory, sink_factory
# AuxiliaryFactory.update_forward_refs()