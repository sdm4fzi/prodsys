from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pydantic import BaseModel, Field, validator
from typing import List, Generator, TYPE_CHECKING

# from process import Process
from simpy import events

from prodsim.simulation import request, sim, state

if TYPE_CHECKING:
    from prodsim.simulation import material, process, state, resources, request, sink


class Controller(ABC, BaseModel):
    control_policy: Callable[[List[request.Request], ], None]
    env: sim.Environment

    resource: resources.Resourcex = Field(init=False, default=None)
    requested: events.Event = Field(init=False, default=None)
    requests: List[request.Request] = Field(init=False, default_factory=list)
    running_processes: List[events.Event] = []

    @validator("requested", pre=True, always=True)
    def init_requested(cls, v, values):
        return events.Event(values["env"])
    
    class Config:
        arbitrary_types_allowed = True

    def set_resource(self, resource: resources.Resourcex) -> None:
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
    def perform_setup(
        self, resource: resources.Resourcex, process: process.Process
    ) -> None:
        pass

    @abstractmethod
    def get_next_material_for_process(
        self, resource: resources.Resourcex, process: process.Process
    ) -> List[material.Material]:
        pass

    @abstractmethod
    def sort_queue(self, _resource: resources.Resourcex):
        pass


class ProductionController(Controller):

    resource: resources.ProductionResource = Field(init=False, default=None)

    def perform_setup(self, resource: resources.Resourcex, process: process.PROCESS_UNION):
        resource.setup(process)

    def get_next_material_for_process(
        self, resource: resources.Resourcex, material: material.Material
    ) -> List[events.Event]:
        events = []
        if isinstance(resource, resources.ProductionResource):
            for queue in resource.input_queues:
                # _material_type = _process.get_raw_material_type()

                # TODO: here should be an advanced process model that controls, which material should be get from which
                events.append(queue.get(filter=lambda item: item is material.material_data))            
            if not events:
                raise ValueError("No material in queue")
            return events
        else:
            raise ValueError("Resource is not a ProductionResource")


    def put_material_to_output_queue(
        self, resource: resources.Resourcex, materials: List[material.Material]
    ) -> List[events.Event]:
        events = []
        if isinstance(resource, resources.ProductionResource):
            for queue in resource.output_queues:
                # _material_type = _process.get_raw_material_type()
                # TODO: implement here a _resource.put_material_of_queues(material)
                for material in materials:
                    events.append(queue.put(material.material_data))
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
            process_request = self.requests.pop(0)
            running_process = self.env.process(self.start_process(process_request))
            self.running_processes.append(running_process)

    def start_process(self, process_request: request.Request):
        resource = process_request.get_resource()
        process = process_request.get_process()
        material = process_request.get_material()

        # yield _resource.setup(_material.next_process)
        with resource.request() as req:
            yield req
            eventss = self.get_next_material_for_process(resource, material)
            yield events.AllOf(resource.env, eventss)
            production_state = resource.get_free_process(process)
            if production_state is None:
                production_state = resource.get_process(process)
            yield production_state.finished_process
            self.run_process(production_state, material)
            yield production_state.finished_process
            production_state.process = None
            eventss = self.put_material_to_output_queue(resource, [material])
            yield events.AllOf(resource.env, eventss)
            for next_material in [material]:
                next_material.finished_process.succeed()

    def run_process(self, input_state: state.State, target_material: material.Material):
        env = input_state.env
        input_state.activate_state()
        input_state.state_info.log_material(target_material, state.StateTypeEnum.production)
        input_state.process = env.process(input_state.process_state())
        # return input_state.process

    def sort_queue(self, resource: resources.Resourcex):
        pass


class TransportController(Controller):
    resource: resources.TransportResource = Field(init=False, default=None)
    requests: List[request.TransportResquest] = Field(default_factory=list)
    control_policy: Callable[[List[request.TransportResquest], ], None]


    def perform_setup(self, resource: resources.Resourcex, process: process.PROCESS_UNION):
        resource.setup(process)

    def get_next_material_for_process(
        self, resource: material.Location, material: material.Material
    ):
        events = []
        if isinstance(resource, resources.ProductionResource) or isinstance(resource, source.Source):
            for queue in resource.output_queues:
                events.append(queue.get(filter=lambda x: x is material.material_data))
            if not events:
                raise ValueError("No material in queue")
        else:
            raise ValueError(f"Resource {resource.data.ID} is not a ProductionResource")
        return events

    def put_material_to_input_queue(
        self, resource: material.Location, material: material.Material
    ) -> List[events.Event]:
        events = []
        if isinstance(resource, resources.ProductionResource) or isinstance(resource, sink.Sink):
            for queue in resource.input_queues:
                events.append(queue.put(material.material_data))
        else:
            raise ValueError(f"Resource {resource.data.ID} is not a ProductionResource")

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
            process_request = self.requests.pop(0)
            running_process = self.env.process(self.start_process(process_request))
            self.running_processes.append(running_process)

    def start_process(self, process_request: request.TransportResquest):
        resource = process_request.get_resource()
        process = process_request.get_process()
        material = process_request.get_material()
        origin = process_request.get_origin()
        target = process_request.get_target()
        
        #TODO: add setup here
        # yield resource.setup(process)
        with resource.request() as req:
            self.sort_queue(resource)
            yield req
            if origin.get_location() != resource.get_location():
                transport_state = resource.get_process(process)
                yield transport_state.finished_process
                self.run_process(transport_state, material, target=origin)
                yield transport_state.finished_process
                transport_state.process = None
                
            eventss = self.get_next_material_for_process(origin, material)
            yield events.AllOf(resource.env, eventss)
            transport_state = resource.get_process(process)
            yield transport_state.finished_process
            self.run_process(transport_state, material, target=target)
            yield transport_state.finished_process
            transport_state.process = None
            eventss = self.put_material_to_input_queue(target, material)
            yield events.AllOf(resource.env, eventss)
            material.finished_process.succeed()

    def sort_queue(self, resource: resources.Resourcex):
        pass

    def run_process(
        self,
        input_state: state.State,
        material: material.Material,
        target: material.Location,
    ):
        env = input_state.env
        target_location = target.get_location()
        input_state.activate_state()
        input_state.state_info.log_material(material, state.StateTypeEnum.transport)
        input_state.state_info.log_target_location(target, state.StateTypeEnum.transport)
        input_state.process = env.process(
            input_state.process_state(target=target_location) # type: ignore False
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


class BatchController(Controller):
    pass

from prodsim.simulation import resources, source, sink
Controller.update_forward_refs()
ProductionController.update_forward_refs()
TransportController.update_forward_refs()