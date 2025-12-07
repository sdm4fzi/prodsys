from typing import Dict, List, Optional, Union, Set


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
        process_candidates = list(
            util.flatten_object(
                [product.process for product in products]
                + [product.transport_process for product in products]
                + [primitive.transport_process for primitive in self.primitives]
                + [resource.processes for resource in self.resources]
            )
        )
        
        processes: List[process.PROCESS_UNION] = []
        visited_process_ids: Set[str] = set()

        def add_process_instance(process_instance: process.PROCESS_UNION) -> None:
            if process_instance is None or not hasattr(process_instance, "ID"):
                return
            process_id = process_instance.ID
            if process_id in visited_process_ids:
                return
            visited_process_ids.add(process_id)
            processes.append(process_instance)
            if isinstance(process_instance, process.ProcessModel):
                for nested_process in process_instance.get_all_nested_processes():
                    add_process_instance(nested_process)

        for process_candidate in process_candidates:
            add_process_instance(process_candidate)

        # Collect processes from states (SetupState, ProcessBreakdownState, etc.)
        states = list(
            util.flatten_object([resource.states for resource in self.resources])
        )
        states = remove_duplicate_items(states)
        
        # Extract processes from states
        state_processes = []
        for state_instance in states:
            if isinstance(state_instance, state.SetupState):
                state_processes.append(state_instance.origin_setup)
                state_processes.append(state_instance.target_setup)
            elif isinstance(state_instance, state.ProcessBreakdownState):
                state_processes.append(state_instance.process)
        
        # Add processes from states to the processes list
        for state_process_instance in state_processes:
            add_process_instance(state_process_instance)
        
        # Build a mapping of process IDs to process objects for resolving ProcessModel references
        process_id_to_process: Dict[str, process.PROCESS_UNION] = {
            proc.ID: proc for proc in processes
        }

        # Extract processes referenced in ProcessModel adjacency matrices
        process_model_processes = []
        for proc in processes:
            if isinstance(proc, process.ProcessModel):
                # Extract all process IDs from the adjacency matrix
                process_ids = set()
                for key in proc.adjacency_matrix.keys():
                    process_ids.add(key)
                for value_list in proc.adjacency_matrix.values():
                    process_ids.update(value_list)
                
                # Find process objects by ID from our mapping
                for process_id in process_ids:
                    if process_id in process_id_to_process:
                        # Already in the list, skip
                        continue
                    # Try to find the process in resources' processes
                    for resource_instance in self.resources:
                        for resource_process in resource_instance.processes:
                            if resource_process.ID == process_id and resource_process not in processes:
                                process_id_to_process[process_id] = resource_process
                                process_model_processes.append(resource_process)
                                break
                        # Also check states for this process
                        for state_instance in resource_instance.states:
                            if isinstance(state_instance, state.SetupState):
                                if state_instance.origin_setup.ID == process_id and state_instance.origin_setup not in processes:
                                    process_id_to_process[process_id] = state_instance.origin_setup
                                    process_model_processes.append(state_instance.origin_setup)
                                if state_instance.target_setup.ID == process_id and state_instance.target_setup not in processes:
                                    process_id_to_process[process_id] = state_instance.target_setup
                                    process_model_processes.append(state_instance.target_setup)
                            elif isinstance(state_instance, state.ProcessBreakdownState):
                                if state_instance.process.ID == process_id and state_instance.process not in processes:
                                    process_id_to_process[process_id] = state_instance.process
                                    process_model_processes.append(state_instance.process)
        
        # Add processes found from ProcessModel adjacency matrices
        for process_model_process in process_model_processes:
            add_process_instance(process_model_process)
        processes = remove_duplicate_items(processes)
        process_id_to_process = {proc.ID: proc for proc in processes}
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

        product_data_models = [product.to_model() for product in products]

        required_process_ids_for_resources: Set[str] = set()
        required_capabilities: Set[str] = set()

        def include_process_id(process_id: Optional[str]) -> None:
            if not process_id:
                return
            process_obj = process_id_to_process.get(process_id)
            if isinstance(process_obj, process.RequiredCapabilityProcess):
                capability = getattr(process_obj, "capability", None)
                if capability:
                    required_capabilities.add(capability)
                return
            required_process_ids_for_resources.add(process_id)
            capability = getattr(process_obj, "capability", None)
            if capability:
                required_capabilities.add(capability)

        for product_data_model in product_data_models:
            processes_field = product_data_model.processes
            if processes_field is None:
                continue
            if isinstance(processes_field, dict):
                for node_id, successors in processes_field.items():
                    include_process_id(node_id)
                    if successors:
                        for successor in successors:
                            include_process_id(successor)
            else:
                flattened = util.flatten_object(processes_field)
                if flattened:
                    for process_id in flattened:
                        include_process_id(process_id)
            include_process_id(product_data_model.transport_process)

        for state_process_instance in state_processes:
            if state_process_instance is None or not hasattr(
                state_process_instance, "ID"
            ):
                continue
            if isinstance(state_process_instance, process.CapabilityProcess):
                if state_process_instance.capability:
                    required_capabilities.add(state_process_instance.capability)
            else:
                capability = getattr(state_process_instance, "capability", None)
                if capability:
                    required_capabilities.add(capability)

        nodes = []
        for process_instance in processes:
            if isinstance(process_instance, process.RequiredCapabilityProcess):
                continue
            for dependency in process_instance.dependencies:
                if not hasattr(dependency, "interaction_node"):
                    continue
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
                if not hasattr(dependency, "interaction_node"):
                    continue
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
        # States are already collected above, no need to collect again

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
        product_data = product_data_models
        resource_model_data = []
        provided_process_ids: Set[str] = set()
        provided_capabilities: Set[str] = set()

        for resource_instance in self.resources:
            resource_model = resource_instance.to_model()
            resource_model_data.append(resource_model)
            for proc_instance in resource_instance.processes:
                if getattr(proc_instance, "ID", None):
                    provided_process_ids.add(proc_instance.ID)
                capability = getattr(proc_instance, "capability", None)
                if capability:
                    provided_capabilities.add(capability)

        missing_process_ids = required_process_ids_for_resources - provided_process_ids
        missing_capabilities = required_capabilities - provided_capabilities

        if missing_process_ids or missing_capabilities:
            message_fragments = []
            if missing_process_ids:
                message_fragments.append(
                    f"Missing resources for processes: {sorted(missing_process_ids)}"
                )
            if missing_capabilities:
                message_fragments.append(
                    f"Missing resources providing capabilities: {sorted(missing_capabilities)}"
                )
            raise ValueError(
                "Production system configuration invalid after process assignment. "
                + " ".join(message_fragments)
            )

        resource_data = resource_model_data
        source_data = [source.to_model() for source in self.sources]
        sink_data = [sink.to_model() for sink in self.sinks]
        dependencies = remove_duplicate_items(dependencies)
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
            dependency_data=dependency_data,
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
