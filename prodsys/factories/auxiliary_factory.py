
from typing import TYPE_CHECKING, Generator, List
from pydantic import BaseModel, Field, parse_obj_as
from prodsys.adapters import adapter
from prodsys.factories import process_factory, queue_factory, resource_factory, sink_factory
from prodsys.models import queue_data, auxiliary_data

from prodsys.simulation import sim, router
from prodsys.simulation import auxiliary, logger


from prodsys.models import source_data
class AuxiliaryFactory(BaseModel):
        """
        Factory class for creating and managing auxiliary objects in the production system.
        """

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
                """
                Create auxiliary objects based on the provided adapter's auxiliary data.

                Args:
                        adapter (adapter.ProductionSystemAdapter): The adapter containing auxiliary data.

                Returns:
                        None
                """
                for auxiliary_data in adapter.auxiliary_data:
                        for i, storage in enumerate(auxiliary_data.initial_quantity_in_stores):
                                stor = auxiliary_data.storages[i]
                                storr = next((storage for storage in adapter.storage_data if storage.ID == stor), None)
                                for _ in range(storage):
                                        auxiliary = self.add_auxiliary(auxiliary_data, storr)
                                        auxiliary.auxiliary_info.log_create_auxiliary(
                                                resource=auxiliary.current_location, _product=auxiliary, event_time=self.env.now
                                        )

        def add_auxiliary(self, auxiliary_data: auxiliary_data.AuxiliaryData, storage: queue_data.StorageData):
                """
                Add a new auxiliary object to the factory.

                Args:
                        auxiliary_data (auxiliary_data.AuxiliaryData): The auxiliary data for the new object.
                        storage (queue_data.StorageData): The storage data for the new object's current location.

                Returns:
                        auxiliary.Auxiliary: The newly created auxiliary object.
                """
                values = {}
                auxiliary_data = auxiliary_data.copy()
                auxiliary_data.ID = (str(auxiliary_data.auxiliary_type) + "_" + str(self.auxiliary_counter))
                values.update({"env": self.env, "data": auxiliary_data})
                transport_process = self.process_factory.get_process(auxiliary_data.transport_process)
                values.update({"transport_process": transport_process})
                storage = self.storage_factory.get_storage(storage.ID)
                values.update({"storage": storage})
                router = self.get_router(source_data.RoutingHeuristic.FIFO)  # Add the routing_heuristic in auxiliary_data, like in source_data
                auxiliary_object = parse_obj_as(auxiliary.Auxiliary, values)
                auxiliary_object.auxiliary_router = router
                auxiliary_object.current_location = storage

                if self.event_logger:
                        self.event_logger.observe_terminal_auxiliary_states(auxiliary_object)

                self.auxiliary_counter += 1
                self.auxiliaries.append(auxiliary_object)
                return auxiliary_object

        def get_auxiliary(self, ID: str) -> auxiliary.Auxiliary:
                """
                Get the auxiliary object with the specified ID.

                Args:
                        ID (str): The ID of the auxiliary object.

                Returns:
                        auxiliary.Auxiliary: The auxiliary object with the specified ID.

                Raises:
                        IndexError: If no auxiliary object with the specified ID is found.
                """
                return [s for s in self.auxiliaries if s.data.ID == ID].pop()

        def get_router(self, routing_heuristic: str):
                """
                Get the router object with the specified routing heuristic.

                Args:
                        routing_heuristic (str): The routing heuristic to use.

                Returns:
                        router.Router: The router object with the specified routing heuristic.
                """
                return router.Router(
                        self.resource_factory,
                        self.sink_factory,
                        self,
                        router.ROUTING_HEURISTIC[routing_heuristic],
                )
        

# from prodsys.factories import resource_factory, sink_factory
# AuxiliaryFactory.update_forward_refs()