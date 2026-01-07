from __future__ import annotations

from typing import Union, Optional, TYPE_CHECKING, List


import logging

from prodsys.simulation.entities.entity import Entity, EntityType
from prodsys.simulation.dependency import DependencyInfo
from prodsys.simulation.product_info import ProductInfo


from simpy import events


if TYPE_CHECKING:
    from prodsys.simulation import product, resources, sink, source
    from prodsys.factories import primitive_factory
    from prodsys.simulation.resources import Resource
    from prodsys.simulation import (
        request,
        process,
        sim,
        state,
    )
    from prodsys.simulation import router as router_module
    from prodsys.simulation.dependency import Dependency, DependedEntity
    from prodsys.simulation import locatable


from prodsys.models import primitives_data

logger = logging.getLogger(__name__)


class Primitive(Entity):
    """
    Class that represents an Primitive in the discrete event simulation. For easier instantion of the class, use the PrimitiveFactory at prodsys.factories.Primitive_factory.
    """

    def __init__(
        self,
        env: sim.Environment,
        data: primitives_data.PrimitiveData,
        transport_process: process.Process,
        storage: port.Store,
    ):
        """
        Initializes the Primitive class.

        Args:
            env (sim.Environment): prodsys simulation environment.
            data (primitives_data.PrimitiveData): Primitive data of the product.
            transport_process (process.Process): Transport process of the primitive.
            storage (port.Store): Storage of the primitive.
        """
        self.env = env
        self.data = data
        self.transport_process = transport_process
        self.storage = storage

        self.router: router_module.Router = None
        self.dependencies: Optional[List[Dependency]] = None
        self.depended_entities: List[DependedEntity] = []
        self._current_locatable: Optional[locatable.Locatable] = None

        self.current_dependant: Union[product.Product, Resource] = None
        self.currently_resolved_dependency: Dependency = None
        self.bound = False
        self.got_free = events.Event(self.env)
        self.finished_process = events.Event(self.env)
        # self.primitive_info = PrimitiveInfo()
        self.dependency_info = DependencyInfo(primitive_id=self.data.ID)
        self.info = ProductInfo(product_ID=self.data.ID)
        self.depended_entities: List[DependedEntity] = []

    @property
    def type(self) -> EntityType:
        return EntityType.PRIMITIVE

    @property
    def size(self) -> int:
        return 1

    def update_location(self, locatable: locatable.Locatable):
        """
        Updates the location of the product object.

        Args:
            locatable (Locatable): Location of the product object.
        """
        self._current_locatable = locatable

    def bind(self, dependant: Union[product.Product, resources.Resource], dependency: Dependency) -> None:
        """
        Reserves the product object.
        """
        if self.bound:
            raise Exception(
                f"Primitive {self.data.ID} is bound reserved. Cannot bind again."
            )
        self.bound = True
        self.current_dependant = dependant
        self.currently_resolved_dependency = dependency
        dependant.depended_entities.append(self)

        self.dependency_info.log_start_dependency(
            event_time=self.env.now,
            requesting_item_id=dependant.data.ID if dependant else None,
            dependency_id=dependency.data.ID,
        )

    def release(self):
        """
        Releases the Primitive from the product after storage of the Primitive.
        """
        self.dependency_info.log_end_dependency(
            event_time=self.env.now,
            requesting_item_id=self.current_dependant.data.ID if self.current_dependant else None,
            dependency_id=self.currently_resolved_dependency.data.ID,
        )
        self._current_locatable = self.current_dependant.current_locatable
        self.current_dependant = None
        self.currently_resolved_dependency = None
        self.bound = False
        self.got_free.succeed()
        self.got_free = events.Event(self.env)


from prodsys.simulation import port
from prodsys.simulation.entities import product
