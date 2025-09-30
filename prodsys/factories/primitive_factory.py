from typing import TYPE_CHECKING, Generator, List, Optional
from prodsys.models import port_data, primitives_data, production_system_data
from prodsys.factories import (
    port_factory,
    process_factory,
    resource_factory,
    sink_factory,
)
from prodsys.models import dependency_data

from prodsys.simulation import primitive, sim
from prodsys.simulation import router as router_module
from prodsys.simulation import logger
from prodsys.models.source_data import RoutingHeuristic
from prodsys.models.product_data import ProductData
from prodsys.models.processes_data import ProcessData
from prodsys.models import source_data


class PrimitiveFactory:
    """
    Factory class for creating and managing Primitive objects in the production system.
    """

    def __init__(
        self,
        env: sim.Environment,
        process_factory: process_factory.ProcessFactory,
        queue_factory: port_factory.QueueFactory,
        resource_factory: resource_factory.ResourceFactory,
        sink_factory: sink_factory.SinkFactory,
        event_logger: Optional[logger.EventLogger] = None,
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
        self.event_logger: Optional[logger.EventLogger] = event_logger
        self.router: router_module.Router = None
        self.primitive_counter = 0

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
                    primitive = self.add_primitive(primitive_data_instance, storage_id)  #was passiert hier, warum ? 

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
            str(primitive_data_instance.ID) + "_" + str(self.primitive_counter)
        )
        values.update({"env": self.env, "data": primitive_data_instance})
        transport_process = self.process_factory.get_process(
            primitive_data_instance.transport_process
        )
        values.update({"transport_process": transport_process})
        storage_from_queue_data = self.queue_factory.get_queue(storage_id)
        values.update({"storage": storage_from_queue_data})
        primitive_object = primitive.Primitive(**values)
        primitive_object.current_locatable = storage_from_queue_data

        if self.event_logger:
            self.event_logger.observe_terminal_primitive_states(primitive_object)

        self.primitive_counter += 1
        self.primitives.append(primitive_object)
        return primitive_object
    
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
            yield from primitive.current_locatable.put(primitive.data)#INFO: gespeicherte DATA Objekte
 
    def get_finished_product_with_type(self, ID: str) -> primitive.product:
        """
        Get the primitive object with the specified ID.

        Args:
            ID (str): The ID of the primitive object.

        Returns:
            primitive.Primitive: The primitive object with the specified ID.

        Raises:
            IndexError: If no auxiliary object with the specified ID is found.
        """
        
        """ try: 
            help =  self.sink_factory.product_factory.finished_products[0] 
        
        
        
        except Exception as e:
            productdata = ProductData(
            ID="product 1",
            description="Product 1 data description",
            type="product 1",
            processes=["production_process"],
            transport_process="NormalTransport",
            )
            product = self.sink_factory.product_factory.create_product(productdata, RoutingHeuristic.random)
            
            return product """
        #TODO: finished product Logik implementieren
        return [s for s in self.primitives if s.data.type == ID].pop()

        
        
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
