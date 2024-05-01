from typing import List, Optional, Union
from uuid import uuid1

from abc import ABC

from pydantic import Field, conlist
from pydantic.dataclasses import dataclass

from prodsys.models import core_asset, source_data, queue_data
import prodsys
from prodsys.util import util

from prodsys.express import (
    core,
    product,
    resources,
    source,
    sink,
    process,
    time_model,
    state,
    process
)


def remove_duplicate_items(
    items: List[
        Union[
            resources.Resource,
            source.Source,
            sink.Sink,
            product.Product,
            state.STATE_UNION,
            process.PROCESS_UNION,
            time_model.TIME_MODEL_UNION,
        ]
    ]
) -> List[
    Union[
        resources.Resource,
        source.Source,
        sink.Sink,
        product.Product,
        state.STATE_UNION,
        process.PROCESS_UNION,
        time_model.TIME_MODEL_UNION,
    ]
]:
    """
    Removes duplicate items from a list of items.
    """
    id_set = set()
    filtered_items = []
    for item in items:
        if item.ID in id_set:
            continue
        id_set.add(item.ID)
        filtered_items.append(item)
    return filtered_items


@dataclass
class ProductionSystem(core.ExpressObject):
    """
    Class that represents a production system. A production system containts of resources, products, sources and sinks.
    It is the `prodsys.express` equivalent to the 'ProductionSystemAdapter' of the `prodsys.adapters` module and
    can be converted to this data object. In contrast to the adapter,
    this class nests the objects in a tree structure, which makes it easier to work with when instantiating
    a production system, but more complicated when reviewing the data itself.

    Args:
        resources (List[resources.Resource]): Resources of the production system.
        sources (List[source.Source]): Sources of the production system.
        sinks (List[sink.Sink]): Sinks of the production system.
    """

    resources: List[Union[resources.ProductionResource, resources.TransportResource]]
    sources: List[source.Source]
    sinks: List[sink.Sink]

    _runner: Optional[prodsys.runner.Runner] = Field(default=None, init=False)

    def to_model(self) -> prodsys.adapters.ProductionSystemAdapter:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            prodsys.adapters.Adapter: An instance of the data object.
        """
        products = [source.product for source in self.sources] + [
            sink.product for sink in self.sinks
        ]
        products = remove_duplicate_items(products)
        processes = list(
            util.flatten_object(
                [product.processes for product in products]+
                [product.transport_process for product in products]
                + [resource.processes for resource in self.resources]
            )
        )
        processes = remove_duplicate_items(processes)

        nodes = []
        for process_instance in processes:
            if not isinstance(process_instance, process.LinkTransportProcess):
                continue
            for link in process_instance.links:
                for node in link:
                    nodes.append(node)
        nodes = remove_duplicate_items(nodes)

        states = list(
            util.flatten_object([resource.states for resource in self.resources])
        )
        states = remove_duplicate_items(states)

        time_models = (
            [process.time_model for process in processes]
            + [state.time_model for state in states]
            + [source.time_model for source in self.sources]
        )
        time_models += [
            s.repair_time_model
            for s in states
            if isinstance(s, state.BreakDownState)
            or isinstance(s, state.ProcessBreakdownState)
        ]
        time_models = remove_duplicate_items(time_models)

        time_model_data = [time_model.to_model() for time_model in time_models]
        process_data = [process.to_model() for process in processes]
        state_data = [state.to_model() for state in states]
        nodes_data = [node.to_model() for node in nodes]
        product_data = [product.to_model() for product in products]
        resource_data = [resource.to_model() for resource in self.resources]
        source_data = [source.to_model() for source in self.sources]
        sink_data = [sink.to_model() for sink in self.sinks]

        queue_data = list(
            util.flatten_object(
                [s._output_queues for s in self.sources]
                + [
                    r._input_queues
                    for r in self.resources
                    if isinstance(r, resources.ProductionResource)
                ]
                + [
                    r._output_queues
                    for r in self.resources
                    if isinstance(r, resources.ProductionResource)
                ]
                + [s._input_queues for s in self.sinks]
            )
        )
        return prodsys.adapters.JsonProductionSystemAdapter(
            time_model_data=time_model_data,
            process_data=process_data,
            state_data=state_data,
            node_data=nodes_data,
            product_data=product_data,
            nodes_data=nodes_data,
            resource_data=resource_data,
            source_data=source_data,
            sink_data=sink_data,
            queue_data=queue_data,
        )

    def run(self, time_range: float = 2880, seed: int = 0):
        """
        Runs the simulation of the production system.
        
        Args:
            time_range (float, optional): The time range of the simulation. Defaults to 2880.
            seed (int, optional): The seed of the simulation. Defaults to 0.
        """
        self._runner = prodsys.runner.Runner(adapter=self.to_model())
        self._runner.adapter.seed = seed
        self._runner.initialize_simulation()
        self._runner.run(time_range)

    def validate(self):
        """
        Validates the production system. Checks if the production system is valid.

        Raises:
            ValueError: If the production system is not valid.
        """
        adapter = self.to_model()
        adapter.validate_configuration()

    @property
    def runner(self):
        if not self._runner:
            raise ValueError(
                "Runner has not been initialized. Please run the simulation first with the run function."
            )
        return self._runner

    @property
    def post_processor(self):
        if not self._runner:
            raise ValueError(
                "Runner has not been initialized. Please run the simulation first with the run function."
            )
        return self._runner.get_post_processor()
