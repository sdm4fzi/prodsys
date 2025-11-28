from __future__ import annotations

from collections.abc import Callable
from pydantic import ConfigDict, Field, field_validator, ValidationInfo
from typing import List, Generator, TYPE_CHECKING, Literal, Optional, Union
import numpy as np
import random

from prodsys.models.processes_data import ProcessTypeEnum
from prodsys.models.port_data import StoreData
from prodsys.models.product_data import ProductData
from prodsys.models.resource_data import ResourceData
from prodsys.simulation.request import RequestType
from prodsys.simulation.request import Request
from prodsys.simulation.entities.product import Product
from prodsys.models.port_data import PortInterfaceType
from prodsys.models.processes_data import ProcessTypeEnum
from prodsys.simulation.product_processor import ProductProcessor


from simpy import events

from prodsys.simulation import (
    port,
    route_finder,
    sim,
    state,
    process,
)

from prodsys.simulation.process import (
    LinkTransportProcess,
    ReworkProcess,
)

if TYPE_CHECKING:
    from prodsys.simulation import (
        process,
        state,
        resources,
        sink,
        source,
    )
    from prodsys.simulation.entities import product
    from prodsys.simulation.entities import primitive
    from prodsys.simulation import request as request_module
    from prodsys.control import sequencing_control_env
    from prodsys.simulation.entities.product import Locatable
    from prodsys.simulation.dependency import Dependency

def get_process_time_for_lots(
            request: request_module.Request
    ) -> float:
        """
        Get the expected process time for a batch of requests.

        Args:
            request (request_module.Request): The request to get the process time for.

        Returns:
            float: The expected process time for the batch.
        """
        if not request.process:
            raise ValueError("Request has no process.")
        return request.process.time_model.get_next_time(
        )    
class DisassemblyProcessHandler:
    
    """
    A production controller is responsible for controlling the processes of a production resource. The controller is requested by products requiring processes. The controller decides has a control policy that determines with which sequence requests are processed.
    """

    def __init__(self, env: sim.Environment) -> None:
        self.env = env
        self.resource = None
        self.process_time: Optional[float] = None
        self.no_sink_transport: bool = False
        
    def get_entities_of_request(
        self, process_request: request_module.Request
    ) -> Generator:
        """
        Get the next product for a process. The product is removed (get) from the input queues of the resource.

        Args:
            process_request (request_module.Request): The request to get the entities from.

        Returns:
            Generator: The generator yields when the product is taken from the queue (multiple events for multiple products, e.g. for a batch process or an assembly).
        """
        for entity in process_request.get_atomic_entities():
            yield from process_request.origin_queue.get(entity.data.ID)

    def put_entities_of_request(
        self, process_request: request_module.Request
    ) -> Generator:
        """
        Place a product to the output queue (put) of the resource.

        Args:
            process_request (request_module.Request): The request to place the product to.

        Returns:
            Generator: The generator yields when the product is placed in the queue (multiple events for multiple products, e.g. for a batch process or an assembly).
        """
        for entity in process_request.get_atomic_entities():
            yield from process_request.target_queue.put(entity.data)


    def set_process_time(self, process_time: float) -> None:
        """
        Set the process time for the production process.

        Args:
            process_time (float): The process time for the production process.
        """
        self.process_time = process_time

    def get_next_product_for_process(
        self, queue: port.Queue, product: product.Product
        
    ) -> Generator:
        """
        Get the next product for a process. The product is removed (get) from the input queues of the resource.

        Args:
            resource (resources.Resource): The resource to take the product from.
            product (product.Product): The product that is requesting the product.

        Returns:
            List[events.Event]: The event that is triggered when the product is taken from the queue (multiple events for multiple products, e.g. for a batch process or an assembly).
        """
      
        yield from queue.get(product.data.ID)

    def put_product_to_output_queue(
        self, queue: port.Queue, product: product.Product
    ) -> Generator:
        """
        Place a product to the output queue (put) of the resource.

        Args:
            resource (resources.Resource): The resource to place the product to.
            products (List[product.Product]): The products to be placed.

        Returns:
            List[events.Event]: The event that is triggered when the product is placed in the queue (multiple events for multiple products, e.g. for a batch process or an assembly).
        """
        yield from queue.put(product.data)
        
    def get_disassembled_product_sink_port(self,product: product.Product ) -> List[float]:
        product_sink = product.router.sink_factory.sinks[product.type]
        
        return product_sink.ports[0].get_location
                
    
            
            
    def handle_request(self, process_request: request_module.Request) -> Generator:
        """
        Start the next process with the following logic:

        1. Setup the resource for the process.
        2. Wait until the resource is free for the process.
        3. Retrieve the product from the queue.
        4. Run the process and wait until finished.
        5. Place the product in the output queue.

        Yields:
            Generator: The generator yields when the process is finished.
        """
        """
        Start the next process with the following logic:

        1. Setup the resource for the process.
        2. Wait until the resource is free for the process.
        3. Retrieve the product from the queue.
        4. Run the process and wait until finished.
        5. Place the product in the output queue.

        Yields:
            Generator: The generator yields when the process is finished.
        """
        resource = process_request.get_resource()
        self.resource = resource
        process = process_request.get_process()

        # Take only dependencies of the main request of the lot
        if process_request.required_dependencies:
            yield process_request.request_dependencies()
        yield from resource.setup(process)
        resource_requests = []
        for _ in range(process_request.capacity_required):
            resource_request = resource.request()
            yield resource_request
            resource_requests.append(resource_request)
        yield from self.get_entities_of_request(process_request)

        process_time = get_process_time_for_lots(process_request)
        resource.controller.mark_started_process(process_request.capacity_required)
        process_state_events = []
        for entity in process_request.get_atomic_entities():
            entity.update_location(process_request.resource)
            production_state: state.State = yield from resource.wait_for_free_process(
                process
            )
            production_state.reserved = True
            process_event = self.env.process(self.run_process(production_state,entity, process, process_time))
            process_state_events.append((process_event, production_state))
        for process_event, production_state in process_state_events:
            yield process_event
            production_state.process = None
        for entity in process_request.get_atomic_entities():    
            yield from self.disassembly(process_request, process_request.target_queue, entity)

        if(self.no_sink_transport):
            buffer_placement_events = []
            for entity in process_request.get_atomic_entities():
                buffer_placement_event = entity.router.request_buffering(process_request)
                if buffer_placement_event:
                    buffer_placement_events.append(buffer_placement_event)
            for buffer_placement_event in buffer_placement_events:
                yield buffer_placement_event

        process_request.entity.router.mark_finished_request(process_request)
        if(self.no_sink_transport):
            self.resource.controller.mark_finished_process_no_sink_transport(process_request, process_request.entity)
        else: 
            self.resource.controller.mark_finished_process(process_request.capacity_required)
        
        for resource_request in resource_requests:
            resource.release(resource_request)
            
    def disassembly(
        self,
        process_request: request_module.Request,
        target_queue: port.Queue,
        product: Product
    ) -> Generator:
        resource = process_request.get_resource()
        process = process_request.get_process()

        disassembled_products: List[Product] = []
        disassembly_list = [ProductData]
        if hasattr(process, "data") and hasattr(process.data, "product_disassembly_dict"):
            disassembly_list = process.data.product_disassembly_dict.get(product.data.type, [])
       
        for dis_product_data in disassembly_list:
            if(dis_product_data.type.__eq__(product.data.type) ):
                disassembled_products.append(product)
                continue
            new_product = product.router.product_factory.create_product(
            dis_product_data  , dis_product_data.routing_heuristic
            )
            disassembled_products.append(new_product)
        if target_queue is None:
            return
        buffer_placement_events = []
        for prod in disassembled_products: 
            yield from target_queue.put(prod.data)
            prod.update_location(target_queue)
            if (prod == product):
                self.no_sink_transport = True
                continue 
            product_processor = ProductProcessor(env=self.env)
            prod.current_process = self.env.process(product_processor.process_product(prod))
            buffer_placement_event = prod.router.request_buffering(process_request)
            if buffer_placement_event:
                buffer_placement_events.append(buffer_placement_event)
        for buffer_placement_event in buffer_placement_events:
                    yield buffer_placement_event

    
    def run_process(
            self,
            input_state: state.State,
            target_product: product.Product,
            process: process.Process,
            process_time: float,
        ) -> Generator:
            """
            Run the process of a product. The process is started and the product is logged.

            Args:
                input_state (state.State): The production state of the process.
                target_product (product.Product): The product that is processed.
                process (process.Process): The process to run.
                process_time (float): The process time.
            """
            input_state.state_info.log_product(
                target_product, state.StateTypeEnum.production
            )
            input_state.process = self.env.process(input_state.process_state(time=process_time))  # type: ignore False
            input_state.reserved = False

            yield input_state.process