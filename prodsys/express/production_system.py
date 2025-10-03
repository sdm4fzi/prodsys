from typing import List, Optional, Union


from pydantic import Field, PrivateAttr
from pydantic.dataclasses import dataclass

from prodsys.express.primitive import Primitive
from prodsys.util import util
from prodsys.models import production_system_data

from prodsys.express import (
    core,
    node,
    resources,
    source,
    time_model,
    state,
    process,
    product,
    sink,
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
    ],
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

    resources: List[Union[resources.Resource]]
    sources: List[source.Source]
    sinks: List[sink.Sink]
    primitives: List[Primitive] = Field(default_factory=list)

    def __post_init__(self):
        self._runner: Optional[runner.Runner] = None

    def to_model(self) -> production_system_data.ProductionSystemData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            prodsys.adapters.Adapter: An instance of the data object.
        """
        products = [source.product for source in self.sources] + [
            sink.product for sink in self.sinks
        ]
        products = remove_duplicate_items(products)
        dependencies = list(
            util.flatten_object([product.dependencies for product in products])
        )
        dependencies += list(
            util.flatten_object([resource.dependencies for resource in self.resources])
        )
        dependencies = remove_duplicate_items(dependencies)
        processes = list(
            util.flatten_object(
                [product.process for product in products]
                + [product.transport_process for product in products]
                + [resource.processes for resource in self.resources]
            )
        )
        processes = remove_duplicate_items(processes)
        dependencies += list(
            util.flatten_object(
                [
                    process_instance.dependencies
                    for process_instance in processes
                    if not isinstance(
                        process_instance, process.RequiredCapabilityProcess
                    )
                ]
            )
        )

        nodes = []
        for process_instance in processes:
            if isinstance(process_instance, process.RequiredCapabilityProcess):
                continue
            for dependency in process_instance.dependencies:
                if dependency.interaction_node:
                    nodes.append(dependency.interaction_node)
            if not isinstance(process_instance, process.LinkTransportProcess):
                continue
            for link in process_instance.links:
                for link_element in link:
                    if isinstance(link_element, node.Node):
                        nodes.append(link_element)
        for resource_instance in self.resources:
            for dependency in resource_instance.dependencies:
                if dependency.interaction_node:
                    nodes.append(dependency.interaction_node)
        nodes = remove_duplicate_items(nodes)
        primitive_stores = list(
            util.flatten_object(
                primitive_store
                for primitive_store in [
                    primitive.storages for primitive in self.primitives
                ]
            )
        )
        primitive_stores = remove_duplicate_items(primitive_stores)
        states = list(
            util.flatten_object([resource.states for resource in self.resources])
        )
        states = remove_duplicate_items(states)

        time_models = (
            [
                process_instance.time_model
                for process_instance in processes
                if not isinstance(process_instance, (process.RequiredCapabilityProcess, process.ProcessModel))
            ]
            + [state_instance.time_model for state_instance in states]
            + [source.time_model for source in self.sources]
        )
        time_models += [
            process_instance.loading_time_model
            for process_instance in processes
            if isinstance(process_instance, process.TransportProcess)
            and process_instance.loading_time_model
        ]
        time_models += [
            process_instance.unloading_time_model
            for process_instance in processes
            if isinstance(process_instance, process.TransportProcess)
            and process_instance.unloading_time_model
        ]
        time_models += [
            s.repair_time_model
            for s in states
            if isinstance(s, state.BreakDownState)
            or isinstance(s, state.ProcessBreakdownState)
        ]
        time_models += [
            s.battery_time_model for s in states if isinstance(s, state.ChargingState)
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
        dependency_data = [dependency.to_model() for dependency in dependencies]
        primitive_data = [
            primitive.to_model() for primitive in self.primitives if primitive.storages
        ]
        primitive_storage_data = [storage.to_model() for storage in primitive_stores]

        ports = list(
            util.flatten_object(
                [s.ports for s in self.sources]
                + [r.ports for r in self.resources if r.ports]
                + [r.buffers for r in self.resources if r.buffers]
                + [s.ports for s in self.sinks]
            )
        )
        port_data = [q.to_model() for q in ports]
        port_data = remove_duplicate_items(port_data)
        return production_system_data.ProductionSystemData(
            time_model_data=time_model_data,
            process_data=process_data,
            state_data=state_data,
            node_data=nodes_data,
            product_data=product_data,
            nodes_data=nodes_data,
            resource_data=resource_data,
            source_data=source_data,
            sink_data=sink_data,
            port_data=port_data + primitive_storage_data,
            depdendency_data=dependency_data,
            primitive_data=primitive_data,
        )

    def run(self, time_range: float = 2880, seed: int = 0):
        """
        Runs the simulation of the production system.

        Args:
            time_range (float, optional): The time range of the simulation. Defaults to 2880.
            seed (int, optional): The seed of the simulation. Defaults to 0.
        """
        self._runner = runner.Runner(production_system_data=self.to_model())
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


from prodsys.simulation import runner
