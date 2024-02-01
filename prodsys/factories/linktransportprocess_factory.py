from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from pydantic import BaseModel, parse_obj_as

from prodsys.factories import time_model_factory, source_factory, sink_factory, resource_factory
from prodsys.simulation import process
from prodsys.models import processes_data

if TYPE_CHECKING:
    from prodsys.adapters import adapter


class LinkTransportProcessFactory(BaseModel):
    """
    Factory class that creates and stores `prodsys.simulation` process objects based on the given process data according to `prodsys.models.processes_data.PROCESS_UNION`.

    Args:
        time_model_factory (time_model_factory.TimeModelFactory): Factory that creates time model objects.
        processes (List[process.PROCESS_UNION], optional): List of process objects. Defaults to [] and is filled by the `create_processes` method.
    """
    time_model_factory: time_model_factory.TimeModelFactory
    source_factory: source_factory.SourceFactory
    sink_factory: sink_factory.SinkFactory
    resource_factory: resource_factory.ResourceFactory
    processes: List[process.PROCESS_UNION] = []

    def create_processes(self, adapter: adapter.ProductionSystemAdapter):
        """
        Creates process objects based on the given adapter.

        Args:
            adapter (adapter.ProductionSystemAdapter): Adapter that contains the process data.
        """
        for process_data in adapter.process_data:
            self.add_processes(process_data, adapter)

    def add_processes(self, process_data: processes_data.PROCESS_DATA_UNION, adapter: adapter.ProductionSystemAdapter):
        values = {}
        if not (isinstance(process_data, processes_data.CompoundProcessData) or isinstance(process_data, processes_data.RequiredCapabilityProcessData)):
            time_model = self.time_model_factory.get_time_model(process_data.time_model_id)
            values.update({"time_model": time_model})
        values.update({"process_data": process_data})
        if isinstance(process_data, processes_data.CompoundProcessData):
            contained_processes_data = [other_process_data for other_process_data in adapter.process_data if other_process_data.ID in process_data.process_ids]
            values.update({"contained_processes_data": contained_processes_data})
        if isinstance(process_data, processes_data.LinkTransportProcessData):
        # 3. Transform Dict_Links to List_links (brauchen wir gerade noch nicht)
        # 4. Assign values.update({"links": ...}) to LinkTransportProcessData
            links_list = []
            for link in process_data.links:
                nodes_list = []
                for node in link:
                    #TODO: nicht sauber gelöst mit wording
                    if "resource" in node:
                        nodes_list.append(self.resource_factory.get_resource(node))
                    elif "source" in node:
                        nodes_list.append(self.source_factory.get_source(node))
                    elif "sink" in node:
                        nodes_list.append(self.sink_factory.get_sink(node))
                    else:
                        nodes_list.append(self.resource_factory.get_node(node))
                links_list.append(nodes_list)
            values.update({"links": links_list})      
        #TODO: Continue here - why do we have in the processes also production_processes? How can i make use of the values?
            
        # 5. Add LinkTransportProcessData to processes of LinkTransportProcessFactory
        x = parse_obj_as(process.PROCESS_UNION, values)
        self.processes.append(x)

    def get_processes_in_order(self, IDs: List[str]) -> List[process.PROCESS_UNION]:
        """
        Returns a list of process objects in the order of the given IDs.

        Args:
            IDs (List[str]): List of IDs that is used to sort the process objects.

        Returns:
            List[process.PROCESS_UNION]: List of process objects in the order of the given IDs.
        """    
        processes = []
        for ID in IDs:
            for _process in self.processes:
                if _process.process_data.ID == ID:
                    processes.append(_process)

        return processes

    def get_process(self, ID: str) -> Optional[process.PROCESS_UNION]:
        """
        Returns a process object based on the given ID.

        Args:
            ID (str): ID of the process object.

        Raises:
            ValueError: If the process object is not found.

        Returns:
            Optional[process.PROCESS_UNION]: Process object based on the given ID.
        """
        pr = [pr for pr in self.processes if pr.process_data.ID in ID]
        if not pr:
            raise ValueError(f"Process with ID {ID} not found")
        return pr.pop()