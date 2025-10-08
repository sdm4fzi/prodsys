from __future__ import annotations

from typing import TYPE_CHECKING, Union, Optional, List

import logging

from prodsys.models.source_data import RoutingHeuristic



from prodsys.models import product_data

from prodsys.simulation.entities.entity import Entity, EntityType


if TYPE_CHECKING:
    from prodsys.simulation.dependency import DependedEntity, Dependency
    from prodsys.simulation import (
        process_models,
        process,
        router,
        sim,
    )
    from prodsys.simulation import locatable
    from prodsys.simulation import product_info

logger = logging.getLogger(__name__)


class Product(Entity):
    """
    Class that represents a product in the discrete event simulation. For easier instantion of the class, use the ProductFactory at prodsys.factories.product_factory.

    Args:
        env (sim.Environment): prodsys simulation environment.
        product_data (product_data.ProductData): Product data that represents the meta information of the simulation product object.
        process_model (proces_models.ProcessModel): Process model that represents the required manufacturing processes and the current state of the product.
        transport_process (process.Process): Transport process that represents the required transport processes.
        product_router (router.Router): Router that is used to route the product object.
    """

    def __init__(
        self,
        env: sim.Environment,
        data: product_data.ProductData,
        process_model: process.ProcessModelProcess,
        transport_process: Union[
            process.TransportProcess,
            process.RequiredCapabilityProcess,
            process.LinkTransportProcess,
        ],
        product_router: router.Router,
        routing_heuristic: RoutingHeuristic,
        info: product_info.ProductInfo,
        dependencies: Optional[List[Dependency]] = None,
    ):
        self.env = env
        self.data = data
        self.process_model = process_model
        self.transport_process = transport_process
        self.router = product_router
        self.routing_heuristic = routing_heuristic
        self.info = info
        self.dependencies: Optional[List[Dependency]] = dependencies
        self.depended_entities: List[DependedEntity] = []

        self.current_locatable: locatable.Locatable = None
        self.current_process: Optional[process.PROCESS_UNION] = None
        
        self.executed_production_processes: List = []

    @property
    def type(self) -> EntityType:
        return EntityType.PRODUCT

    @property
    def size(self) -> int:
        return 1

    def update_location(self, locatable: locatable.Locatable):
        """
        Updates the location of the product object.

        Args:
            locatable (locatable.Locatable): Locatable objects where product object currently is.
        """
        self.current_locatable = locatable


from prodsys.simulation import process
