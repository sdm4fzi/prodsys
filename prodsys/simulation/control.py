from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pydantic import BaseModel, Field, validator, Extra
from typing import List, Generator, TYPE_CHECKING

# from process import Process
from simpy import events

from prodsys.simulation import request, sim, state

if TYPE_CHECKING:
    from prodsys.simulation import product, process, state, resources, request, sink
    from prodsys.util import gym_env


class Controller(ABC, BaseModel):
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
    running_processes: List[events.Event] = []

    @validator("requested", pre=True, always=True)
    def init_requested(cls, v, values):
        return events.Event(values["env"])

    class Config:
        arbitrary_types_allowed = True
        extra=Extra.allow

    def set_resource(self, resource: resources.Resource) -> None:
        self.resource = resource
        self.env = resource.env

    def request(self, process_request: request.Request) -> None:
        self.requests.append(process_request)
        if not self.requested.triggered:
            self.requested.succeed()

    @abstractmethod
    def control_loop(self) -> None:
        pass

    @abstractmethod
    def get_next_product_for_process(
        self, resource: resources.Resource, process: process.Process
    ) -> List[product.Product]:
        pass

    @abstractmethod
    def sort_queue(self, _resource: resources.Resource):
        pass


class ProductionController(Controller):
    resource: resources.ProductionResource = Field(init=False, default=None)

    def get_next_product_for_process(
        self, resource: resources.Resource, product: product.Product
    ) -> List[events.Event]:
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
        events = []
        if isinstance(resource, resources.ProductionResource):
            for queue in resource.output_queues:
                for product in products:
                    events.append(queue.put(product.product_data))
        else:
            raise ValueError("Resource is not a ProductionResource")

        return events

    def control_loop(self) -> Generator:
        while True:
            yield events.AnyOf(
                env=self.env, events=self.running_processes + [self.requested]
            )
            if self.requested.triggered:
                self.requested = events.Event(self.env)
            else:
                for process in self.running_processes:
                    if process.triggered:
                        self.running_processes.remove(process)
            if (
                len(self.running_processes) == self.resource.capacity
                or not self.requests
            ):
                continue
            self.control_policy(self.requests)
            running_process = self.env.process(self.start_process())
            self.running_processes.append(running_process)

    def start_process(self) -> Generator:
        yield self.env.timeout(0)
        process_request = self.requests.pop(0)
        resource = process_request.get_resource()
        process = process_request.get_process()
        product = process_request.get_product()
        yield resource.setup(process)
        with resource.request() as req:
            yield req
            eventss = self.get_next_product_for_process(resource, product)
            yield events.AllOf(resource.env, eventss)
            production_state = resource.get_free_process(process)
            if production_state is None:
                production_state = resource.get_process(process)
            yield production_state.finished_process
            self.run_process(production_state, product)
            yield production_state.finished_process
            production_state.process = None
            eventss = self.put_product_to_output_queue(resource, [product])
            yield events.AllOf(resource.env, eventss)
            for next_product in [product]:
                if not resource.got_free.triggered:
                    resource.got_free.succeed()
                next_product.finished_process.succeed()

    def run_process(self, input_state: state.State, target_product: product.Product):
        env = input_state.env
        input_state.prepare_for_run()
        input_state.state_info.log_product(
            target_product, state.StateTypeEnum.production
        )
        target_product.product_info.log_start_process(
            target_product.next_resource,
            target_product,
            self.env.now,
            state.StateTypeEnum.production,
        )
        input_state.process = env.process(input_state.process_state())

    def sort_queue(self, resource: resources.Resource):
        pass


class TransportController(Controller):
    resource: resources.TransportResource = Field(init=False, default=None)
    requests: List[request.TransportResquest] = Field(default_factory=list)
    control_policy: Callable[
        [
            List[request.TransportResquest],
        ],
        None,
    ]

    def get_next_product_for_process(
        self, resource: product.Location, product: product.Product
    ):
        events = []
        if isinstance(resource, resources.ProductionResource) or isinstance(
            resource, source.Source
        ):
            for queue in resource.output_queues:
                events.append(queue.get(filter=lambda x: x is product.product_data))
            if not events:
                raise ValueError("No product in queue")
        else:
            raise ValueError(f"Resource {resource.data.ID} is not a ProductionResource")
        return events

    def put_product_to_input_queue(
        self, resource: product.Location, product: product.Product
    ) -> List[events.Event]:
        events = []
        if isinstance(resource, resources.ProductionResource) or isinstance(
            resource, sink.Sink
        ):
            for queue in resource.input_queues:
                events.append(queue.put(product.product_data))
        else:
            raise ValueError(
                f"Resource {resource.data.ID} is not a ProductionResource or Sink"
            )

        return events

    def control_loop(self) -> Generator:
        while True:
            yield events.AnyOf(
                env=self.env, events=self.running_processes + [self.requested]
            )
            if self.requested.triggered:
                self.requested = events.Event(self.env)
            else:
                for process in self.running_processes:
                    if process.triggered:
                        self.running_processes.remove(process)

            if (
                len(self.running_processes) == self.resource.capacity
                or not self.requests
            ):
                continue
            self.control_policy(self.requests)
            running_process = self.env.process(self.start_process())
            self.running_processes.append(running_process)

    def start_process(self) -> Generator:
        yield self.env.timeout(0)
        process_request = self.requests.pop(0)

        resource = process_request.get_resource()
        process = process_request.get_process()
        product = process_request.get_product()
        origin = process_request.get_origin()
        target = process_request.get_target()

        yield resource.setup(process)
        with resource.request() as req:
            self.sort_queue(resource)
            yield req
            if origin.get_location() != resource.get_location():
                transport_state = resource.get_process(process)
                yield transport_state.finished_process
                self.run_process(transport_state, product, target=origin)
                yield transport_state.finished_process
                transport_state.process = None

            eventss = self.get_next_product_for_process(origin, product)
            yield events.AllOf(resource.env, eventss)
            transport_state = resource.get_process(process)
            yield transport_state.finished_process
            self.run_process(transport_state, product, target=target)
            yield transport_state.finished_process
            transport_state.process = None
            eventss = self.put_product_to_input_queue(target, product)
            yield events.AllOf(resource.env, eventss)
            if isinstance(target, resources.ProductionResource):
                target.unreserve_input_queues()
            product.finished_process.succeed()

    def sort_queue(self, resource: resources.Resource):
        pass

    def run_process(
        self,
        input_state: state.State,
        product: product.Product,
        target: product.Location,
    ):
        env = input_state.env
        target_location = target.get_location()
        input_state.prepare_for_run()
        input_state.state_info.log_product(product, state.StateTypeEnum.transport)
        input_state.state_info.log_target_location(
            target, state.StateTypeEnum.transport
        )
        product.product_info.log_start_process(
            product.next_resource,
            product,
            self.env.now,
            state.StateTypeEnum.transport,
        )
        input_state.process = env.process(
            input_state.process_state(target=target_location)  # type: ignore False
        )


def FIFO_control_policy(requests: List[request.Request]) -> None:
    pass


def LIFO_control_policy(requests: List[request.Request]) -> None:
    requests.reverse()


def SPT_control_policy(requests: List[request.Request]) -> None:
    requests.sort(key=lambda x: x.process.get_expected_process_time())


def SPT_transport_control_policy(requests: List[request.TransportResquest]) -> None:
    requests.sort(
        key=lambda x: x.process.get_expected_process_time(
            x.origin.get_location(), x.target.get_location()
        )
    )


def agent_control_policy(
    gym_env: gym_env.ProductionControlEnv, requests: List[request.Request]
) -> None:
    gym_env.interrupt_simulation_event.succeed()


class BatchController(Controller):
    pass


from prodsys.simulation import resources, source, sink

Controller.update_forward_refs()
ProductionController.update_forward_refs()
TransportController.update_forward_refs()
