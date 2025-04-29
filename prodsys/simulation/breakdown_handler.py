from dataclasses import dataclass
from random import sample
import random
from prodsys.adapters.adapter import ProductionSystemAdapter, get_missing_capability_processes, get_missing_production_processes, get_missing_transport_processes, get_production_resources, get_required_production_processes, get_required_transport_processes, get_required_capability_processes, get_available_production_processes, get_available_transport_processes, get_available_capability_processes, get_transport_resources 
from prodsys.models import processes_data
from prodsys.simulation.logger import EventLogger
from prodsys.simulation.process_matcher import ProcessMatcher
from prodsys.simulation.resources import Resource
from prodsys.factories.resource_factory import ResourceFactory
from prodsys.models.processes_data import PROCESS_DATA_UNION
from prodsys.simulation.sim import Environment

@dataclass
class MovedProcess:
    """
    Represents a process that has been moved from one resource to another.
    """
    process_id: str
    from_resource_id: str
    to_resource_id: str


class BreakdownHandler:
    """
    Handles breakdowns in the production system.
    """

    def __init__(self, adapter: ProductionSystemAdapter, env: Environment, resource_factory: ResourceFactory, process_matcher: ProcessMatcher, logger: EventLogger):
        self.original_adapter = adapter.model_copy(deep=True)
        self.adapter = adapter
        self.env = env
        self.resource_factory = resource_factory
        self.process_factory = resource_factory.process_factory
        self.process_matcher = process_matcher
        self.logger = logger

        self.moved_processes: list[MovedProcess] = []

    def handle_breakdown(self, resource: Resource):
        # checks if the processes of the resource exist somewhere else -> if not add them to other resources with an allocation policy
        active_resources = [r for r in self.resource_factory.resources if r.data.ID != resource.data.ID and r.active.triggered]
        active_resource_data = [r.data for r in active_resources]
        self.adapter.resource_data = active_resource_data

        required_production_processes = get_required_production_processes(self.adapter)
        required_transport_processes = get_required_transport_processes(self.adapter)
        required_capability_processes = get_required_capability_processes(self.adapter)

        available_production_processes = get_available_production_processes(self.adapter)
        available_transport_processes = get_available_transport_processes(self.adapter)
        available_capability_processes = get_available_capability_processes(self.adapter)
        
        missing_production_processes = get_missing_production_processes(available_production_processes, required_production_processes)
        missing_transport_processes = get_missing_transport_processes(available_transport_processes, required_transport_processes)
        missing_capability_processes = get_missing_capability_processes(available_capability_processes, required_capability_processes)

        missing_processes = missing_production_processes + missing_transport_processes + missing_capability_processes

        if not missing_processes:
            return

        for missing_process in missing_processes:
            # check if the process is available in the active resources
            updated_resource = self.allocate_process(missing_process)
            moved_process = MovedProcess(process_id=missing_process.ID, from_resource_id=resource.data.ID, to_resource_id=updated_resource.data.ID)
            self.moved_processes.append(moved_process)
        self.process_matcher.precompute_compatibility_tables()

    def allocate_process(self, process: PROCESS_DATA_UNION) -> Resource:
        """
        Allocates a process to an active resource.
        """
        print("Allocating process:", process.ID)
        if self.adapter.scenario_data:
            max_processes = self.adapter.scenario_data.constraints.max_num_processes_per_machine
        else:
            max_processes = 10
        if isinstance(process, processes_data.TransportProcessData):
            relevant_resource_data = get_transport_resources(self.adapter)
        else:
            relevant_resource_data = get_production_resources(self.adapter)
        relevant_resource_ids = [r.ID for r in relevant_resource_data]
        # TODO: also update setup states from resource before
        resources_with_free_capacity = [
            r
            for r in self.resource_factory.resources
            if r.data.ID in relevant_resource_ids and len(self._get_combined_compound_processes(r.data.process_ids)) < max_processes
        ]
        if not resources_with_free_capacity:
            return
        sampled_resource = random.choice(resources_with_free_capacity)

        updated_resource = self.resource_factory.add_process_to_resource(sampled_resource, process.ID)
        # observe added production state
        for state in updated_resource.production_states:
            if not state.state_data.ID == process.ID:
                continue
            self.logger.observe_resource_state(state)
        return updated_resource

    def _get_combined_compound_processes(self, process_ids: list[str]) -> list[PROCESS_DATA_UNION]:
        """
        Returns a list of compound processes that are combined from the given process IDs.
        """
        compund_processes = [
            process
            for process in self.adapter.process_data
            if isinstance(process, processes_data.CompoundProcessData)
        ]
        process_id_set = set(process_ids)
        combined_processes = []
        for process in compund_processes:
            if set(process.process_ids).issubset(process_id_set):
                combined_processes.append(process)
        all_contained_processes = set()
        for process in combined_processes:
            all_contained_processes.update(process.process_ids)
        not_combined_processes = process_id_set - all_contained_processes
        combined_processes.extend(
            [process for process in self.adapter.process_data if process.ID in not_combined_processes]
        )
        return combined_processes

    def handle_reactivation(self, resource: Resource):
        pass
        # relevant_moved_processes = [mp for mp in self.moved_processes if mp.from_resource_id == resource.data.ID]
        # if not relevant_moved_processes:
        #     return
        # for moved_process in relevant_moved_processes:
        #     # check if the process is available in the active resources
        #     resource_to_remove_process_from = self.resource_factory.get_resource(moved_process.to_resource_id)
        #     self.resource_factory.remove_process_from_resource(resource_to_remove_process_from, moved_process.process_id)

        # # add deactivated resource again to the adapter
        # self.adapter.resource_data.append(resource.data)
        # self.process_matcher.precompute_compatibility_tables()
        # self.moved_processes = [mp for mp in self.moved_processes if mp.from_resource_id != resource.data.ID]
