from __future__ import annotations

from abc import ABC
from enum import Enum
from collections.abc import Iterable
from typing import List, Protocol, Union, Optional, TYPE_CHECKING, Generator

from pydantic import BaseModel, ConfigDict, Field

import logging

logger = logging.getLogger(__name__)

from simpy import events

from pydantic import BaseModel
from prodsys.simulation import primitive, router as router_module

if TYPE_CHECKING:
    from prodsys.simulation import product, resources, sink, source
    from prodsys.factories import auxiliary_factory

from prodsys.models import dependency_data
from prodsys.simulation import (
    request,
    process,
    sim,
    store,
    state,
)

class DependedEntity(Protocol):
    """
    Protocol that defines the interface for a depended entity. This is used to define the type of the depended entity in the Dependency class.
    """
    def bind(self, dependant: process.Process | resources.Resource | primitive.Primitive) -> None:
        """
        Binds the depended entity to the dependency.
        """
        pass
        # When binding the items, they should be transport to the location of destination 
        # they should go in a status so that they are not used elsewhere, until release is called.

    def release(self):
        """
        Releases the product object.
        """
        pass
        # release should make DependedEntity available for other processes
        # called by the dependant 

    # TODO: use these function and consider them for state / product_info logging, also add logging to primitives

class Dependency:
    """
    Class that represents an auxiliary in the discrete event simulation. For easier instantion of the class, use the AuxiliaryFactory at prodsys.factories.auxiliary_factory.

    Args:
        env (sim.Environment): prodsys simulation environment.
        auxilary_data (auxilary.Auxilary): Auxilary data of the product.
    """

    env: sim.Environment
    data: dependency_data.DependencyData
    required_process: process.Process
    required_primitive: primitive.Primitive
    required_resource: resources.Resource

    def __init__(
        self,
        env: sim.Environment,
        data: dependency_data.DependencyData,
        required_process: process.Process,
        required_primitive: primitive.Primitive,
        required_resource: resources.Resource,
    ):
        """
        Initializes the Auxiliary class.

        Args:
            env (sim.Environment): prodsys simulation environment.
            auxilary_data (auxilary.Auxilary): Auxilary data of the product.
            transport_process (process.Process): Transport process of the product.
            storage (store.Store): Storage of the product.
            relevant_processes (List[Union[process.ProductionProcess, process.CapabilityProcess]]): Relevant processes of the product.
            relevant_transport_processes (List[process.TransportProcess]): Relevant transport processes of the product.
        """
        self.env = env
        self.data = data
        self.required_process = required_process
        self.required_primitive = required_primitive
        self.required_resource = required_resource

from prodsys.simulation import product
