from __future__ import annotations

from typing import List, TYPE_CHECKING, Tuple

from pydantic import BaseModel, Field
from simpy import events

from prodsys.simulation import router, sim, store, time_model
from prodsys.data_structures import source_data, product_data

if TYPE_CHECKING:
    from prodsys.factories import product_factory


class Source(BaseModel):
    env: sim.Environment
    data: source_data.SourceData
    product_data: product_data.ProductData
    product_factory: product_factory.ProductFactory
    time_model: time_model.TimeModel
    router: router.Router
    output_queues: List[store.Queue] = Field(default_factory=list, init=False)

    class Config:
        arbitrary_types_allowed = True

    def add_output_queues(self, output_queues: List[store.Queue]):
        self.output_queues.extend(output_queues)

    def start_source(self):
        self.env.process(self.create_product_loop())

    def create_product_loop(self):
        while True:
            yield self.env.timeout(self.time_model.get_next_time())
            product = self.product_factory.create_product(
                self.product_data, self.router
            )
            available_events_events = []
            for queue in self.output_queues:
                available_events_events.append(queue.put(product.product_data))
            yield events.AllOf(self.env, available_events_events)

            product.process = self.env.process(product.process_product())
            product.next_resource = self

    def get_location(self) -> List[float]:
        return self.data.location
    
from prodsys.factories import product_factory
Source.update_forward_refs()