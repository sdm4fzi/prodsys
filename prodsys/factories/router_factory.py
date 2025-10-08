from __future__ import annotations

from typing import TYPE_CHECKING

from prodsys.simulation import sim
from prodsys.simulation import router as router_module

if TYPE_CHECKING:
    from prodsys.simulation import sim
    from prodsys.factories import (
        resource_factory,
        sink_factory,
        product_factory,
        source_factory,
        primitive_factory,
    )
    from prodsys.models import production_system_data

class RouterFactory:
    def __init__(
        self,
        env: sim.Environment,
        resource_factory: resource_factory.ResourceFactory,
        sink_factory: sink_factory.SinkFactory,
        product_factory: product_factory.ProductFactory,
        source_factory: source_factory.SourceFactory,
        primitive_factory: primitive_factory.PrimitiveFactory,
        production_system_data: production_system_data.ProductionSystemData,
    ):
        self.env = env
        self.resource_factory = resource_factory
        self.sink_factory = sink_factory
        self.product_factory = product_factory
        self.source_factory = source_factory
        self.primitive_factory = primitive_factory
        self.production_system_data = production_system_data

        self.system_routers: dict[str, router_module.Router] = {}
        self.global_system_router: router_module.Router = None

    def create_routers(self):
        for system_sources in self.resource_factory.system_resources.values():
            system_sources.router = router_module.Router(
                env=self.env,
                resource_factory=self.resource_factory,
                sink_factory=self.sink_factory,
                product_factory=self.product_factory,
                source_factory=self.source_factory,
                primitive_factory=self.primitive_factory,
                production_system_data=self.production_system_data,
                resources=system_sources.subresources,
            )
            self.system_routers[system_sources.data.ID] = system_sources.router
            system_sources.set_router(system_sources.router)

        global_system_router = router_module.Router(
            env=self.env,
            resource_factory=self.resource_factory,
            sink_factory=self.sink_factory,
            product_factory=self.product_factory,
            source_factory=self.source_factory,
            primitive_factory=self.primitive_factory,
            production_system_data=self.production_system_data,
            resources=self.resource_factory.global_system_resource.subresources,
        )
        self.global_system_router = global_system_router
        self.resource_factory.global_system_resource.set_router(global_system_router)

    def start_routers(self):
        for router in self.system_routers.values():
            self.env.process(router.resource_routing_loop())
            self.env.process(router.primitive_routing_loop())
        self.env.process(self.global_system_router.resource_routing_loop())
        self.env.process(self.global_system_router.primitive_routing_loop())