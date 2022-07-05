from __future__ import annotations

from abc import ABC, abstractmethod
from tracemalloc import start
from typing import List, Tuple
from collections.abc import Callable

import env
import material
import process
import resource
import state
# from process import Process
from dataclasses import dataclass
import simpy
@dataclass
class Controller(ABC):
    # TODO: look at the Mesa package for the implementation of their controller or data_logger
    control_policy: Callable[[List[material.Material]], List[material.Material]]

    @abstractmethod
    def perform_setup(self, _resource: resource.Resource, _process: process.Process):
        pass

    @abstractmethod
    def get_next_material_for_process(self, _resource: resource.Resource, _process: process.Process) -> List[material.Material]:
        pass

    @abstractmethod
    def request(self, _process: process.Process, _resource: resource.Resource, _material: material.Material):
        pass

    @abstractmethod
    def sort_queue(self, _resource: resource.Resource):
        pass


class SimpleController(Controller):
    def __init__(self, _control_policy: Callable[[List[material.Material]], List[material.Material]]):
        self.control_policy = _control_policy
        self.next_materials = None
        requests = None

    def perform_setup(self, _resource: resource.Resource, _process: process.Process):
        _resource.setup(_process)

    def get_next_material_for_process(self, _resource: resource.Resource, _process: process.Process):
        events = []
        for queue in _resource.input_queues:
            # _material_type = _process.get_raw_material_type()

            # TODO: here should be an advanced process model that controls, which material should be get from which
            #  queue
            events.append(queue.get(filter=lambda x: x.next_resource is _resource))
        return events

    def put_material_to_output_queue(self, _resource: resource.Resource, _materials: List[material.Material]) -> None:
        events = []
        for queue in _resource.output_queues:
            # _material_type = _process.get_raw_material_type()
            # TODO: implement here a _resource.put_material_of_queues(material)
            for material in _materials:
                events.append(queue.put(material))

        return events

    def request(self, _process: process.Process, _resource: resource.Resource, _material: material.Material):
        # TODO: implement setup of resources in case of a process change instead of this overwriting of the setup
        _resource.current_process = _process
        # yield _resource.setup(_material.next_process)
        with _resource.request() as req:
            self.sort_queue(_resource)
            yield req
            events = self.get_next_material_for_process(_resource, _process)
            yield simpy.AllOf(_resource.env, events)
            next_materials = [event.value for event in events]
            production_state = _resource.get_free_process(_process)
            if production_state is None:
                production_state = _resource.get_process(_process)
            yield production_state.finished_process
            yield self.run_process(production_state, _material)
            production_state.process = None
            events = self.put_material_to_output_queue(_resource, next_materials)
            yield simpy.AllOf(_resource.env, events)
            for next_material in next_materials:
                next_material.finished_process.succeed()

    def run_process(self, input_state: state.State, target_material: material.Material):
        _env =  input_state.env
        input_state.activate_state()
        input_state.state_info.log_material(target_material)
        input_state.process = _env.process(input_state.process_state())
        return input_state.process


    def sort_queue(self, _resource: resource.Resource):
        pass

class TransportController(Controller):
    def __init__(self, _control_policy: Callable[[List[material.Material]], List[material.Material]]):
        self.control_policy = _control_policy
        self.next_materials = None

    def perform_setup(self, _resource: resource.Resource, _process: process.Process):
        _resource.setup(_process)
    
    def get_next_material_for_process(self, _resource: resource.Resource, _material: material.Material):
        events = []
        for queue in _resource.output_queues:
            # _material_type = _process.get_raw_material_type()

            # TODO: here should be an advanced process model that controls, which material should be get from which
            #  queue
            events.append(queue.get(filter=lambda x: x is _material))
        return events

    def put_material_to_input_queue(self, _resource: resource.Resource, _material: material.Material) -> None:
        events = []
        for queue in _resource.input_queues:
            # _material_type = _process.get_raw_material_type()
            # TODO: implement here a _resource.put_material_of_queues(material)
            events.append(queue.put(_material))

        return events

    def request(self, _process: process.Process, _resource: resource.Resource, origin: resource.Resource, target: resource.Resource, 
        _material: material.Material):
        # TODO: implement setup of resources in case of a process change instead of this overwriting of the setup
        _resource.current_process = _process
        # yield _resource.setup(_material.next_process)
        with _resource.request() as req:
            self.sort_queue(_resource)
            yield req
            if origin.get_location() != _resource.get_location():
                transport_state = _resource.get_process(_process)
                yield transport_state.finished_process
                yield self.run_process(transport_state, _material, target=origin)
                transport_state.process = None
            events = self.get_next_material_for_process(origin, _material)
            yield simpy.AllOf(_resource.env, events)
            transport_state = _resource.get_process(_process)
            yield transport_state.finished_process
            yield self.run_process(transport_state, _material, target=target)
            transport_state.process = None
            events = self.put_material_to_input_queue(target, _material)
            yield simpy.AllOf(_resource.env, events)
            _material.finished_process.succeed()


    def sort_queue(self, _resource: resource.Resource):
        pass

    def run_process(self, input_state: state.State, _material: material.Material, target: resource.Resource):
        _env =  input_state.env
        target_location = target.get_location()
        input_state.activate_state()
        input_state.state_info.log_material(_material)
        input_state.state_info.log_target_location(target)
        input_state.process = _env.process(input_state.process_state(target=target_location))
        return input_state.process


def FIFO_control_policy(current: List[material.Material]) -> List[material.Material]:
    return current.copy()


def LIFO_control_policy(current: List[material.Material]) -> List[material.Material]:
    return list(reversed(current))


def SPT_control_policy(current: List[material.Material]) -> List[material.Material]:
    current.sort(key=lambda x: x.process_time)
    return list(current)


class BatchController(Controller):
    pass