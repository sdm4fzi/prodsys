from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pydantic import BaseModel, Field, validator, Extra
from typing import Any, List, Generator, TYPE_CHECKING, Union, Optional
import numpy as np

import logging

logger = logging.getLogger(__name__)

# from process import Process
from simpy import events

from prodsys.simulation import node, request, route_finder, sim, state, process

from prodsys.simulation.process import LinkTransportProcess, RequiredCapabilityProcess, ProductionProcess, ReworkProcess

if TYPE_CHECKING:
    from prodsys.simulation import product, process, state, resources, request, sink, source
    from prodsys.control import sequencing_control_env
    from prodsys.simulation.product import Locatable



class Controller(ABC, BaseModel):
    """
    A controller is responsible for controlling the processes of a resource. The controller is requested by products requiring processes. The controller decides has a control policy that determines with which sequence requests are processed.

    Args:
        control_policy (Callable[[List[request.Request]], None]): The control policy that determines the sequence of requests to be processed.
        env (sim.Environment): The environment in which the controller is running.

    Attributes:
        resource (resources.Resource): The resource that is controlled by the controller.
        requested (events.Event): An event that is triggered when a request is made to the controller.
        requests (List[request.Request]): A list of requests that are made to the controller.
        running_processes (List[events.Event]): A list of (simpy) processes that are currently running on the resource.
    """

    control_policy: Callable[
        [
            List[request.Request],
        ],
        None,
    ]
    env: sim.Environment

    resource: resources.Resource = Field(init=False, default=None)
    requested: events.Event = Field(init=False, default=None)
    requests: List[request.Request] = Field(init=False, default_factory=list)
    running_processes: List[events.Process] = []
    reserved_requests_count: int = 0

    @validator("requested", pre=True, always=True)
    def init_requested(cls, v, values):
        return events.Event(values["env"])

    class Config:
        arbitrary_types_allowed = True
        extra = Extra.allow

    def set_resource(self, resource: resources.Resource) -> None:
        self.resource = resource
        self.env = resource.env

    def request(self, process_request: request.Request) -> None:
        """
        Request the controller consider the request in the future for processing.

        Args:
            process_request (request.Request): The request to be processed.
        """
        self.requests.append(process_request)
        logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Got requested by {process_request.product.product_data.ID}"})
        if not self.requested.triggered:
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": "Triggered requested event"})
            self.requested.succeed()

    def wait_for_free_process(self, resource: resources.Resource, process: process.Process) -> Generator[state.State, None, None]:
        """
        Wait for a free process of a resource.

        Args:
            resource (resources.TransportResource): The resource.
            process (process.Process): The process.

        Returns:
            Generator: The generator yields when a process is free.

        Yields:
            Generator: The generator yields when a process is free.
        """
        possible_states = resource.get_processes(process)
        while True:
            free_state = resource.get_free_process(process)
            if free_state is not None:
                return free_state
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Waiting for free process"})
            yield events.AnyOf(
                self.env,
                [
                    state.process
                    for state in possible_states
                    if state.process is not None and state.process.is_alive
                ],
            )
    

    @abstractmethod
    def control_loop(self) -> None:
        """
        The control loop is the main process of the controller. It has to run indefinetely.
        It should repeatedly check if requests are made or a process is finished and then start the next process.
        """
        pass

    @abstractmethod
    def get_next_product_for_process(
        self, resource: resources.Resource, process: process.Process
    ) -> List[events.Event]:
        """
        Get the next product for a process. The product is removed (get) from the queues.

        Args:
            resource (resources.Resource): The resource to take the product from.
            process (process.Process): The process that is requesting the product.

        Returns:
            List[events.Event]: The event that is triggered when the product is taken from the queue (multiple events for multiple products, e.g. for a batch process or an assembly).
        """
        pass


class ProductionController(Controller):
    """
    A production controller is responsible for controlling the processes of a production resource. The controller is requested by products requiring processes. The controller decides has a control policy that determines with which sequence requests are processed.
    """
    resource: resources.ProductionResource = Field(init=False, default=None)
    rework_needed: Optional[bool] = None
    blocking: Optional[bool] = None

    def get_next_product_for_process(
        self, resource: resources.Resource, product: product.Product
    ) -> List[events.Event]:
        """
        Get the next product for a process. The product is removed (get) from the input queues of the resource.

        Args:
            resource (resources.Resource): The resource to take the product from.
            product (product.Product): The product that is requesting the product.

        Returns:
            List[events.Event]: The event that is triggered when the product is taken from the queue (multiple events for multiple products, e.g. for a batch process or an assembly).
        """
        events = []
        if isinstance(resource, resources.ProductionResource):
            for queue in resource.input_queues:
                events.append(
                    queue.get(filter=lambda item: item is product.product_data)
                )
            if not events:
                raise ValueError("No product in queue")
            return events
        else:
            raise ValueError("Resource is not a ProductionResource")

    def put_product_to_output_queue(
        self, resource: resources.Resource, products: List[product.Product]
    ) -> List[events.Event]:
        """
        Place a product to the output queue (put) of the resource.

        Args:
            resource (resources.Resource): The resource to place the product to.
            products (List[product.Product]): The products to be placed.

        Returns:
            List[events.Event]: The event that is triggered when the product is placed in the queue (multiple events for multiple products, e.g. for a batch process or an assembly).
        """
        events = []
        if isinstance(resource, resources.ProductionResource):
            for queue in resource.output_queues:
                for product in products:
                    events.append(queue.put(product.product_data))
        else:
            raise ValueError("Resource is not a ProductionResource")

        return events

    def control_loop(self) -> Generator:
        """
        The control loop is the main process of the controller. It has to run indefinetely.

        The logic is the control loop of a production resource is the following:

        1. Wait until a request is made or a process is finished.
        2. If a request is made, add it to the list of requests.
        3. If a process is finished, remove it from the list of running processes.
        4. If the resource is full or there are no requests, go to 1.
        5. Sort the queue according to the control policy.
        6. Start the next process. Go to 1.

        Yields:
            Generator: The generator yields when a request is made or a process is finished.
        """
        while True:
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": "Waiting for request or process to finish"})
            yield events.AnyOf(
                env=self.env, events=self.running_processes + [self.requested]
            )
            if self.requested.triggered:
                self.requested = events.Event(self.env)
            for process in self.running_processes:
                if not process.is_alive:
                    self.running_processes.remove(process)
            if self.resource.full or not self.requests or self.reserved_requests_count == len(self.requests):
                logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"No request ({len(self.requests)}) or resource full ({self.resource.full}) or all requests reserved ({self.reserved_requests_count == len(self.requests)})"})
                continue
            self.control_policy(self.requests)
            self.reserved_requests_count += 1
            running_process = self.env.process(self.start_process())
            self.running_processes.append(running_process)
            if not self.resource.full:
                logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": "Triggered requested event after process"})
                self.requested.succeed()

    def start_process(self) -> Generator:
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
        logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Starting process"})
        yield self.env.timeout(0)
        process_request = self.requests.pop(0)
        self.reserved_requests_count -= 1
        resource = process_request.get_resource()
        process = process_request.get_process()
        product = process_request.get_product()
        logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Starting setup for process for {product.product_data.ID}"})

        yield self.env.process(resource.setup(process))
        with resource.request() as req:
            yield req
            product_retrieval_events = self.get_next_product_for_process(resource, product)
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Waiting to retrieve product {product.product_data.ID} from queue"})
            yield events.AllOf(resource.env, product_retrieval_events)
            
            production_state: state.State = yield self.env.process(self.wait_for_free_process(resource, process))
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Starting process for {product.product_data.ID}"})
            yield self.env.process(self.run_process(production_state, product, process))
            production_state.process = None
            self.rework_needed = False
            
            product_put_events = self.put_product_to_output_queue(resource, [product])
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Waiting to put product {product.product_data.ID} to queue"})
            yield events.AllOf(resource.env, product_put_events)
            
            for next_product in [product]:
                if not resource.got_free.triggered:
                    resource.got_free.succeed()
                next_product.finished_process.succeed()
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Finished process for {product.product_data.ID}"})
    
    def run_process(self, input_state: state.State, target_product: product.Product, process: process.Process):
        """
        Run the process of a product. The process is started and the product is logged.

        Args:
            input_state (state.State): The production state of the process.
            target_product (product.Product): The product that is processed.
        """
        input_state.prepare_for_run()
        input_state.state_info.log_product(
            target_product, state.StateTypeEnum.production
        )
        target_product.product_info.log_start_process(
            self.resource,
            target_product,
            self.env.now,
            state.StateTypeEnum.production,
        )
        input_state.process = self.env.process(input_state.process_state())
        self.blocking = self.check_blocking(target_product, process)
        self.rework_needed = self.handle_rework(process)
        
        if self.rework_needed is not None:
            target_product.rework_needed = self.rework_needed
            if self.rework_needed:
                target_product.processes_needing_rework = target_product.processes_needing_rework or []
                target_product.processes_needing_rework.append(process)
            
            #target_product.product_info.log_rework(target_product)
            #print(f"Product {target_product.product_data.ID} needs rework: {self.rework_needed}")

        yield input_state.process
    
    def check_blocking(self, product: product.Product, proc: process.Process) -> bool:

        blocking = False  
        for proc in self.resource.processes:
            if isinstance(proc, ReworkProcess):
                blocking = proc.process_data.blocking
                if blocking is not None:
                    product.blocking = blocking
                    return blocking
        return blocking

    def handle_rework(self, process: process.Process) -> bool:
        """
        Determine if rework is needed based on the process's failure rate.

        Args:
            process (process.Process): The process to check for failure rate.

        Returns:
            bool: True if rework is needed, False otherwise.
        """
        failure_rate = process.process_data.failure_rate
        if failure_rate is not None:
            self.rework_needed = np.random.choice([True, False], p=[failure_rate, 1-failure_rate])
        return self.rework_needed

class BatchController(Controller):
    """
    A production controller is responsible for controlling the processes of a production resource. The controller is requested by products requiring processes. The controller decides has a control policy that determines with which sequence requests are processed.
    """
    resource: resources.ProductionResource = Field(init=False, default=None)

    def get_batch_size(self, resource: resources.Resource) -> int:
        """
        Get the batch size for the given resource which equals the capacity of the resource.

        Args:
            resource (resources.Resource): The resource to get the batch size for.

        Returns:
            int: The batch size of the resource.
        """
        if isinstance(resource, resources.ProductionResource):
            return resource.capacity
        else:
            raise ValueError("Resource is not a ProductionResource")

    def get_next_product_for_process(
        self, resource: resources.Resource, process_request: request.Request
    ) -> Generator:
        """
       Get the next batch of products for a process. The products are removed (get) from the input queues of the resource.

        Args:
            resource (resources.Resource): The resource to take the products from.
            process_request (request.Request): The request that is requesting the products.

        Returns:
            List[events.Event]: The events that are triggered when the products are taken from the queue.
        """

        events = []
        products = []
        batch_size = self.get_batch_size(resource) 
        if isinstance(resource, resources.ProductionResource):
            for queue in resource.input_queues:
                while len(products) < batch_size:
                    event = queue.get(filter=lambda item: item.ID == process_request.get_product().product_data.ID)
                    events.append(event)
                    product = yield event
                    products.append(product)
            if not events:
                raise ValueError("Not enough products in queue for a batch")
            return events
        else:
            raise ValueError("Resource is not a ProductionResource")

    def put_product_to_output_queue(
        self, resource: resources.Resource, products: List[product.Product]
    ) -> List[events.Event]:
        """
        Place a batch of products to the output queue (put) of the resource.

        Args:
            resource (resources.Resource): The resource to place the product to.
            products (List[product.Product]): The products to be placed.

        Returns:
            List[events.Event]: The event that is triggered when the product is placed in the queue (multiple events for multiple products, e.g. for a batch process or an assembly).
        """
        events = []
        if isinstance(resource, resources.ProductionResource):
            for queue in resource.output_queues:
                for product in products:
                    events.append(queue.put(product.product_data))
        else:
            raise ValueError("Resource is not a ProductionResource")

        return events

    def control_loop(self) -> Generator:
        """
        The control loop is the main process of the controller. It has to run indefinetely.

        The logic is the control loop of a production resource is the following:

        1. Wait until a request is made or a process is finished.
        2. If a request is made, add it to the list of requests.
        3. If a process is finished, remove it from the list of running processes.
        4. If the resource is full or there are not enough requests for a batch, go to 1.
        5. Sort the queue according to the control policy.
        6. Start the next process. Go to 1.

        Yields:
            Generator: The generator yields when a request is made or a process is finished.
        """
        while True:
            batch_size = self.get_batch_size(self.resource)
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": "Waiting for request or process to finish"})
            yield events.AnyOf(
                env=self.env, events=self.running_processes + [self.requested]
            )
            if self.requested.triggered:
                self.requested = events.Event(self.env)
            for process in self.running_processes:
                if not process.is_alive:
                    self.running_processes.remove(process)
            if self.resource.full or len(self.requests) < batch_size or self.reserved_requests_count == len(self.requests):
                logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Not enough requests ({len(self.requests)}) or resource full ({self.resource.full}) or all requests reserved ({self.reserved_requests_count == len(self.requests)})"})
                continue
            self.control_policy(self.requests)
            self.reserved_requests_count += 1
            running_process = self.env.process(self.start_process())
            self.running_processes.append(running_process)
            if not self.resource.full:
                logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": "Triggered requested event after process"})
                self.requested.succeed()

    def start_process(self) -> Generator:
        """
        Start the next process with the following logic:

        1. Setup the resource for the process.
        2. Wait until the resource is free for the process.
        3. Retrieve the products for the batch from the queue.
        4. Run the process and wait until finished.
        5. Place the product in the output queue.

        Yields:
            Generator: The generator yields when the process is finished.
        """
        batch_size = self.get_batch_size(self.resource)
        logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Starting batch process"})
        yield self.env.timeout(0)
        process_request = self.requests.pop(0)
        self.reserved_requests_count -= 1
        resource = process_request.get_resource()
        process = process_request.get_process()
        product = process_request.get_product()
        products = [process_request.get_product() for _ in range(batch_size)]
        logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Starting setup for process for {product.product_data.ID} with batch size {batch_size}"})

        yield self.env.process(resource.setup(process))
        with resource.request() as req:
            yield req
            product_retrieval_events = yield from self.get_next_product_for_process(resource, process_request)
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Waiting to retrieve products for batch from queue"})
            yield events.AllOf(resource.env, product_retrieval_events)
            
            production_state: state.State = yield self.env.process(self.wait_for_free_process(resource, process))
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Starting batch process"})
            yield self.env.process(self.run_process(production_state, products))
            production_state.process = None
            
            product_put_events = yield from self.put_product_to_output_queue(resource, products)
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Waiting to put products to queue"})
            yield events.AllOf(resource.env, product_put_events)
            
            for product in products:
                if not resource.got_free.triggered:
                    resource.got_free.succeed()
                product.finished_process.succeed()
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Finished batch process"})
    
    def run_process(self, input_state: state.State, products: List[product.Product]):
        """
        Run the process of a product. The process is started and the product is logged.

        Args:
            input_state (state.State): The production state of the process.
            target_product (product.Product): The product that is processed.
        """
        input_state.prepare_for_run()
        for product in products:
            input_state.state_info.log_product(
                product, state.StateTypeEnum.production
            )
            product.product_info.log_start_process(
                self.resource,
                product,
                self.env.now,
                state.StateTypeEnum.production,
            )
        input_state.process = self.env.process(input_state.process_state())
        # TODO: if performed process has failure_rate -> sample (np.choice) if failure happened, if so: mark product as rework_needed
        yield input_state.process

class TransportController(Controller):
    """
    Controller for transport resources.
    """
    resource: resources.TransportResource = Field(init=False, default=None)
    requests: List[request.TransportResquest] = Field(default_factory=list)
    control_policy: Callable[
        [
            List[request.TransportResquest],
        ],
        None,
    ]
    _current_locatable: Optional[product.Locatable] = Field(init=False, default=None)

    def get_next_product_for_process(
        self, resource: product.Locatable, product: product.Product
    ) -> List[events.Event]:
        """
        Get the next product for a process from the input queue of a resource.

        Args:
            resource (product.Locatable): Resource or Source to get the product from.
            product (product.Product): The product that shall be transported.

        Raises:
            ValueError: If the product is not in the queue.
            ValueError: If the resource is not a  ProductionResource or Source.

        Returns:
            List[events.Event]: The event that is triggered when the product is in the queue.
        """
        events = []
        if isinstance(resource, resources.ProductionResource) or isinstance(
            resource, source.Source
        ):
            for queue in resource.output_queues:
                events.append(queue.get(filter=lambda x: x is product.product_data))
            if not events:
                raise ValueError("No product in queue")
        else:
            raise ValueError(f"Resource {resource.data.ID} is not a ProductionResource or Source")
        return events

    def put_product_to_input_queue(
        self, locatable: product.Locatable, product: product.Product
    ) -> List[events.Event]:
        """
        Put a product to the input queue of a resource.

        Args:
            locatable (product.Locatable): Resource or Sink to put the product to.
            product (product.Product): The product that shall be transported.

        Raises:
            ValueError: If the resource is not a  ProductionResource or Sink.

        Returns:
            List[events.Event]: The event that is triggered when the product is in the queue.
        """
        events = []
        if isinstance(locatable, resources.ProductionResource) or isinstance(
            locatable, sink.Sink
        ):
            for queue in locatable.input_queues:
                events.append(queue.put(product.product_data))
        else:
            raise ValueError(
                f"Resource {locatable.data.ID} is not a ProductionResource or Sink"
            )

        return events

    def control_loop(self) -> Generator:
        """
        The control loop is the main process of the controller. It has to run indefinetely.

        The logic is the control loop of a production resource is the following:

        1. Wait until a request is made or a process is finished.
        2. If a request is made, add it to the list of requests.
        3. If a process is finished, remove it from the list of running processes.
        4. If the resource is full or there are no requests, go to 1.
        5. Sort the queue according to the control policy.
        6. Start the next process. Go to 1.

        Yields:
            Generator: The generator yields when a request is made or a process is finished.
        """
        self.update_location(self.resource)
        while True:
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": "Waiting for request or process to finish"})
            yield events.AnyOf(
                env=self.env, events=self.running_processes + [self.requested]
            )
            if self.requested.triggered:
                self.requested = events.Event(self.env)
            for process in self.running_processes:
                if not process.is_alive:
                    self.running_processes.remove(process)
            if self.resource.full or not self.requests:
                logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"No request ({len(self.requests)}) or resource full ({self.resource.full})"})
                continue
            self.control_policy(self.requests)
            running_process = self.env.process(self.start_process())
            self.running_processes.append(running_process)
            if not self.resource.full:
                logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": "Triggered requested event after process"})
                self.requested.succeed()

    def update_location(self, locatable: product.Locatable) -> None:
        """
        Set the current position of the transport resource.

        Args:
            locatable (product.Locatable): The current position.
        """
        self._current_locatable = locatable
        self.resource.set_location(locatable.get_location())

    def start_process(self) -> Generator:
        """
        Start the next process.

        The logic is the following:

        1. Get the next request.
        2. Get the resource, process, product, origin and target from the request.
        3. Setup the resource for the process.
        4. Wait until the resource is free.
        5. If the origin is not the location of the transport resource, wait until the transport is free.
        6. Move transport resource to the origin.
        7. Get the product from the origin.
        8. Move transport resource to the target.
        9. Put the product to the target.
        10. Go to 1.


        Yields:
            Generator: The generator yields when the transport is over.
        """
        yield self.env.timeout(0)
        process_request = self.requests.pop(0)

        resource = process_request.get_resource()
        process = process_request.get_process()
        product = process_request.get_product()
        origin = process_request.get_origin()
        target = process_request.get_target()
        route_to_target = process_request.get_route()
        logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Starting setup for process for {product.product_data.ID}"})

        yield self.env.process(resource.setup(process))
        with resource.request() as req:
            yield req
            # TODO: adjust logic, that get_location function also handels the case for a resource with different input and output locations.
            # TODO: use below a function to get the output location of the origin
            if origin.get_location() != resource.get_location():
                route_to_origin = self.find_route_to_origin(process_request)
                logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Empty transport needed for {product.product_data.ID} from {origin.data.ID} to {target.data.ID}"})
                transport_state: state.State = yield self.env.process(self.wait_for_free_process(resource, process))
                logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Starting transport to pick up {product.product_data.ID} for transport"})
                yield self.env.process(self.run_transport(transport_state, product, route_to_origin, empty_transport=True))

            product_retrieval_events = self.get_next_product_for_process(origin, product)
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Waiting to retrieve product {product.product_data.ID} from queue"})
            yield events.AllOf(resource.env, product_retrieval_events)
            product.update_location(self.resource)

            transport_state: state.State = yield self.env.process(self.wait_for_free_process(resource, process))
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Starting transport of {product.product_data.ID}"})
            yield self.env.process(self.run_transport(transport_state, product, route_to_target, empty_transport=False))
            
            product_put_events = self.put_product_to_input_queue(target, product)
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Waiting to put product {product.product_data.ID} to queue"})
            yield events.AllOf(resource.env, product_put_events)
            product.update_location(target)
            
            if isinstance(target, resources.ProductionResource):
                target.unreserve_input_queues()
            if not resource.got_free.triggered:
                resource.got_free.succeed()
            product.finished_process.succeed()
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Finished transport of {product.product_data.ID}"})

    def run_transport(self, transport_state: state.State, product: product.Product, route: List[product.Locatable], empty_transport: bool) -> Generator:
        """
        Run the transport process and every single transport step in the route of the transport process.

        Args:
            transport_state (state.State): The transport state of the process.
            product (product.Product): The product that is transported.
            route (List[product.Locatable]): The route of the transport with locatable objects.
            empty_transport (bool): If the transport is empty.

        Yields:
            Generator: The generator yields when the transport is over.
        """
        for link_index, (location, next_location) in enumerate(zip(route, route[1:])):
            if link_index == 0:
                initial_transport_step = True
            else:
                initial_transport_step = False
            if link_index == len(route) - 2:
                last_transport_step = True
            else:
                last_transport_step = False
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Moving from {location.data.ID} to {next_location.data.ID}", "empty_transport": True, "initial_transport_step": initial_transport_step, "last_transport_step": last_transport_step})
            yield self.env.process(self.run_process(transport_state, product, target=next_location, empty_transport=empty_transport, initial_transport_step=initial_transport_step, last_transport_step=last_transport_step))
            self.update_location(next_location)
            logger.debug({"ID": "controller", "sim_time": self.env.now, "resource": self.resource.data.ID, "event": f"Arrived at {next_location.data.ID}", "empty_transport": True, "initial_transport_step": initial_transport_step, "last_transport_step": last_transport_step})
            transport_state.process = None

    def run_process(
        self,
        input_state: state.TransportState,
        product: product.Product,
        target: product.Locatable,
        empty_transport: bool,
        initial_transport_step: bool,
        last_transport_step: bool
    ):
        """
        Run the process of a product. The process is started and the product is logged.

        Args:
            input_state (state.State): The transport state of the process.
            product (product.Product): The product that is transported.
            target (product.Locatable): The target of the transport.
            empty_transport (bool): If the transport is empty.
            initial_transport_step (bool): If this is the initial transport step.
            last_transport_step (bool): If this is the last transport step.
        """
        target_location = target.get_location()
        input_state.prepare_for_run()
        input_state.state_info.log_product(product, state.StateTypeEnum.transport)
        if self._current_locatable.data.ID is self.resource.data.ID:
            origin = None
        else:
            origin = self._current_locatable
        input_state.state_info.log_transport(
            origin,
            target, state.StateTypeEnum.transport,
            empty_transport=empty_transport
        )
        product.product_info.log_start_process(
            self.resource,
            product,
            self.env.now,
            state.StateTypeEnum.transport,
        )
       
        input_state.process = self.env.process(
            input_state.process_state(target=target_location, initial_transport_step=initial_transport_step, last_transport_step=last_transport_step)  # type: ignore False
        )
        yield input_state.process

    def find_route_to_origin(self, process_request: request.TransportResquest) -> List[product.Locatable]:
        """
        Find the route to the origin of the transport request.

        Args:
            process_request (request.TransportResquest): The transport request.

        Returns:
            List[product.Locatable]: The route to the origin. In case of a simple transport process, the route is just the origin.
        """
        if isinstance(process_request.process, LinkTransportProcess):
            route_to_origin = route_finder.find_route(request=process_request, find_route_to_origin=True, process=process_request.get_process())
            if not route_to_origin:
                raise ValueError(f"Route to origin for transport of {process_request.product.product_data.ID} could not be found. Router selected a transport resource that can perform the transport but does not reach the origin.")
            return route_to_origin
        else:
            return [self._current_locatable, process_request.get_origin()]


def FIFO_control_policy(requests: List[request.Request]) -> None:
    """
    Sort the requests according to the FIFO principle.

    Args:
        requests (List[request.Request]): The list of requests.
    """
    pass


def LIFO_control_policy(requests: List[request.Request]) -> None:
    """
    Sort the requests according to the LIFO principle (reverse the list).

    Args:
        requests (List[request.Request]): The list of requests.
    """
    requests.reverse()


def SPT_control_policy(requests: List[request.Request]) -> None:
    """
    Sort the requests according to the SPT principle (shortest process time first).

    Args:
        requests (List[request.Request]): The list of requests.
    """
    requests.sort(key=lambda x: x.process.get_expected_process_time())


def SPT_transport_control_policy(requests: List[request.TransportResquest]) -> None:
    """
    Sort the requests according to the SPT principle (shortest process time first).

    Args:
        requests (List[request.TransportResquest]): The list of requests.
    """
    requests.sort(
        key=lambda x: x.process.get_expected_process_time(
            x.origin.get_location(), x.target.get_location()
        )
    )
def nearest_origin_and_longest_target_queues_transport_control_policy(requests: List[request.TransportResquest]) -> None:
    """
    Sort the requests according to nearest origin without considering the target location. 
    Second order sorting by descending length of the target output queues, to prefer targets where a product can be picked up.
    Args:
        requests (List[request.TransportResquest]): The list of requests.
    """
    requests.sort(
        key=lambda x: (
            x.process.get_expected_process_time(
                x.resource.data.location, x.origin.get_location()),
                - x.target.get_output_queue_length()
                )
    )

def nearest_origin_and_shortest_target_input_queues_transport_control_policy(requests: List[request.TransportResquest]) -> None:
    """
    Sort the requests according to nearest origin without considering the target location.
    Second order sorting by ascending length of the target input queue so that resources with empty input queues get material to process.

    Args:
        requests (List[request.TransportResquest]): The list of requests.
    """
    requests.sort(
        key=lambda x: (
            x.process.get_expected_process_time(
                x.resource.data.location, x.origin.get_location()),
            x.target.get_input_queue_length()
            )
    )

def agent_control_policy(
    gym_env: sequencing_control_env.AbstractSequencingControlEnv, requests: List[request.Request]
) -> None:
    """
    Sort the requests according to the agent's policy.

    Args:
        gym_env (gym_env.ProductionControlEnv): A gym environment, where the agent can interact with the simulation.
        requests (List[request.Request]): The list of requests.
    """
    gym_env.interrupt_simulation_event.succeed()


from prodsys.simulation import resources, source, sink

Controller.update_forward_refs()
ProductionController.update_forward_refs()
BatchController.update_forward_refs()
TransportController.update_forward_refs()
