from __future__ import annotations
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Tuple

import simpy

import resource
import material
import request

class Environment(simpy.Environment):

    def __init__(self) -> None:
        super().__init__()

    def set_resource_factory(self, resource_factory: resource.ResourceFactory) -> None:
        self.resource_factory = resource_factory

    def get_next_process(self, material: material.Material):
        pass

    def get_next_resource(self, resource: resource.Resource):
        pass

    def request_process_of_resource(self, request: request.Request) -> None:
        _controller = request.get_resource().get_controller()
        # self.process(_controller.request(request))
        _controller.request(request)