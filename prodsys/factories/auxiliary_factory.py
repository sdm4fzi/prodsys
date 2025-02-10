from typing import TYPE_CHECKING, Generator, List
from pydantic import BaseModel, ConfigDict, Field
from prodsys.adapters import adapter
from prodsys.factories import (
    process_factory,
    queue_factory,
    resource_factory,
    sink_factory,
)
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
    queue_factory: queue_factory.QueueFactory
    resource_factory: resource_factory.ResourceFactory
    sink_factory: sink_factory.SinkFactory
    auxiliaries: List[auxiliary.Auxiliary] = []
    event_logger: logger.EventLogger = Field(default=False, init=False)
    auxiliary_counter: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def create_auxiliary(self, adapter: adapter.ProductionSystemAdapter):
        """
        Create auxiliary objects based on the provided adapter's auxiliary data.

        Args:
            adapter (adapter.ProductionSystemAdapter): The adapter containing auxiliary data.
        """
        for auxiliary_data in adapter.auxiliary_data:
            for i, capacity_auxiliary_in_storage in enumerate(
                auxiliary_data.quantity_in_storages
            ):
                storage_id = auxiliary_data.storages[i]
                storage = next(
                    (
                        storage
                        for storage in adapter.queue_data
                        if storage.ID == storage_id
                    ),
                    None,
                )
                for _ in range(capacity_auxiliary_in_storage):
                    auxiliary = self.add_auxiliary(auxiliary_data, storage)
                    auxiliary.auxiliary_info.log_create_auxiliary(
                        resource=auxiliary.current_locatable,
                        _product=auxiliary,
                        event_time=self.env.now,
                    )

    def add_auxiliary(
        self,
        auxiliary_data: auxiliary_data.AuxiliaryData,
        storage: queue_data.StoreData,
    ) -> auxiliary.Auxiliary:
        """
        Add a new auxiliary object to the factory.

        Args:
                auxiliary_data (auxiliary_data.AuxiliaryData): The auxiliary data for the new object.
                storage (queue_data.QueueData): The storage data for the new object's current location.

        Returns:
                auxiliary.Auxiliary: The newly created auxiliary object.
        """
        values = {}
        auxiliary_data = auxiliary_data.model_copy(deep=True)
        auxiliary_data.ID = (
            str(auxiliary_data.auxiliary_type) + "_" + str(self.auxiliary_counter)
        )
        values.update({"env": self.env, "data": auxiliary_data})
        transport_process = self.process_factory.get_process(
            auxiliary_data.transport_process
        )
        values.update({"transport_process": transport_process})
        relevant_processes = []
        for process_id in auxiliary_data.relevant_processes:
            relevant_processes.append(self.process_factory.get_process(process_id))
        values.update({"relevant_processes": relevant_processes})
        relevant_transport_processes = []
        for transport_process_id in auxiliary_data.relevant_transport_processes:
            relevant_transport_processes.append(
                self.process_factory.get_process(transport_process_id)
            )
        values.update({"relevant_transport_processes": relevant_transport_processes})
        storage_from_queue_data = self.queue_factory.get_queue(storage.ID)
        values.update({"storage": storage_from_queue_data})
        router = self.get_router(
            source_data.RoutingHeuristic.FIFO
        )  # Add the routing_heuristic in auxiliary_data, like in source_data
        auxiliary_object = auxiliary.Auxiliary.model_validate(values)
        auxiliary_object.auxiliary_router = router
        auxiliary_object.current_locatable = storage_from_queue_data
        auxiliary_object.init_got_free()

        if self.event_logger:
            self.event_logger.observe_terminal_auxiliary_states(auxiliary_object)

        self.auxiliary_counter += 1
        self.auxiliaries.append(auxiliary_object)
        return auxiliary_object

    def place_auxiliaries_in_queues(self):
        """
        Place the auxiliary objects in the system.
        """
        for auxiliary in self.auxiliaries:
            auxiliary.current_locatable.put(auxiliary.product_data)

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

AuxiliaryFactory.model_rebuild()