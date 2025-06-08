from typing import TYPE_CHECKING, Generator, List
from prodsys.models import primitives_data, production_system_data
from prodsys.factories import (
    process_factory,
    queue_factory,
    resource_factory,
    sink_factory,
)
from prodsys.models import dependency_data, queue_data

from prodsys.simulation import primitive, sim
from prodsys.simulation import router as router_module
from prodsys.simulation import logger


from prodsys.models import source_data


class PrimitiveFactory:
    """
    Factory class for creating and managing Primitive objects in the production system.
    """

    def __init__(
        self,
        env: sim.Environment,
        process_factory: process_factory.ProcessFactory,
        queue_factory: queue_factory.QueueFactory,
        resource_factory: resource_factory.ResourceFactory,
        sink_factory: sink_factory.SinkFactory,
    ):
        """
        Initialize the PrimitiveFactory with the given environment and factories.

        Args:
            env (sim.Environment): The simulation environment.
            process_factory (process_factory.ProcessFactory): The process factory.
            queue_factory (queue_factory.QueueFactory): The queue factory.
            resource_factory (resource_factory.ResourceFactory): The resource factory.
            sink_factory (sink_factory.SinkFactory): The sink factory.
        """
        self.env = env
        self.process_factory = process_factory
        self.queue_factory = queue_factory
        self.resource_factory = resource_factory
        self.sink_factory = sink_factory

        self.primitives: List[primitive.Primitive] = []
        self.event_logger: logger.EventLogger = None
        self.router: router_module.Router = None
        self.auxiliary_counter = 0

    def create_primitives(self, adapter: production_system_data.ProductionSystemData):
        """
        Create primitive objects based on the provided adapter's primitive data.

        Args:
            adapter (adapter.ProductionSystemAdapter): The adapter containing primitive data.
        """
        for primitive_data_instance in adapter.primitive_data:
            # if isinstance(primitive_data_instance, primitives_data.StoredPrimitive):
            #     primitives = self.create_stored_primitives(primitive_data_instance, adapter)
            #     self.primitives.extend(primitives)
            for storage_id, quantity_in_storage in zip(
                primitive_data_instance.storages,
                primitive_data_instance.quantity_in_storages,
            ):
                for _ in range(quantity_in_storage):
                    primitive = self.add_primitive(primitive_data_instance, storage_id)

    def add_primitive(
        self, primitive_data_instance: primitives_data.PrimitiveData, storage_id: str
    ) -> primitive.Primitive:
        """
        Add a new auxiliary object to the factory.

        Args:
                primitive_data_instance (primitives_data.PrimitiveData): The primitive data for the new object.
                storage (queue_data.QueueData): The storage data for the new object's current location.

        Returns:
                primitive.Primitive: The newly created primitive object.
        """
        values = {}
        primitive_data_instance = primitive_data_instance.model_copy(deep=True)
        primitive_data_instance.ID = (
            str(primitive_data_instance.ID) + "_" + str(self.auxiliary_counter)
        )
        values.update({"env": self.env, "data": primitive_data_instance})
        transport_process = self.process_factory.get_process(
            primitive_data_instance.transport_process
        )
        values.update({"transport_process": transport_process})
        storage_from_queue_data = self.queue_factory.get_queue(storage_id)
        values.update({"storage": storage_from_queue_data})
        auxiliary_object = primitive.Primitive(**values)
        auxiliary_object.current_locatable = storage_from_queue_data

        if self.event_logger:
            self.event_logger.observe_terminal_primitive_states(auxiliary_object)

        self.auxiliary_counter += 1
        self.primitives.append(auxiliary_object)
        return auxiliary_object
    
    def set_router(self, router: router_module.Router) -> None:
        """
        Set the router for the factory.

        Args:
            router (router_module.Router): The router to be set.
        """
        self.router = router
        for primitive in self.primitives:
            primitive.router = self.router

    def place_primitives_in_queues(self) -> Generator:
        """
        Place the auxiliary objects in the system.
        """
        for primitive in self.primitives:
            yield from primitive.current_locatable.put(primitive.data)

    def get_primitive_with_type(self, ID: str) -> primitive.Primitive:
        """
        Get the primitive object with the specified ID.

        Args:
            ID (str): The ID of the primitive object.

        Returns:
            primitive.Primitive: The primitive object with the specified ID.

        Raises:
            IndexError: If no auxiliary object with the specified ID is found.
        """
        return [s for s in self.primitives if s.data.type == ID].pop()


# AuxiliaryFactory.model_rebuild()
