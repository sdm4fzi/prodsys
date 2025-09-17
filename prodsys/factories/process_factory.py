from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

from prodsys.factories import time_model_factory
from prodsys.models import processes_data
from prodsys.simulation import process


if TYPE_CHECKING:
    from prodsys.models import production_system_data

PROCESS_MAP = {
    processes_data.ProcessTypeEnum.ProductionProcesses: process.ProductionProcess,
    processes_data.ProcessTypeEnum.TransportProcesses: process.TransportProcess,
    processes_data.ProcessTypeEnum.ReworkProcesses: process.ReworkProcess,
    processes_data.ProcessTypeEnum.CapabilityProcesses: process.CapabilityProcess,
    processes_data.ProcessTypeEnum.CompoundProcesses: process.CompoundProcess,
    processes_data.ProcessTypeEnum.LinkTransportProcesses: process.LinkTransportProcess,
    processes_data.ProcessTypeEnum.RequiredCapabilityProcesses: process.RequiredCapabilityProcess,
    processes_data.ProcessTypeEnum.ProcessModels: process.ProcessModelProcess,
    processes_data.ProcessTypeEnum.LoadingProcesses: process.LoadingProcess,
}


class ProcessFactory:
    """
    Factory class that creates and stores `prodsys.simulation` process objects based on the given process data according to `prodsys.models.processes_data.PROCESS_UNION`.

    Args:
        time_model_factory (time_model_factory.TimeModelFactory): Factory that creates time model objects.
        processes (List[process.PROCESS_UNION], optional): List of process objects. Defaults to [] and is filled by the `create_processes` method.
    """

    def __init__(self, time_model_factory: time_model_factory.TimeModelFactory):
        """
        Initializes the ProcessFactory with the given time model factory.

        Args:
            time_model_factory (time_model_factory.TimeModelFactory): Factory that creates time model objects.
        """
        self.time_model_factory = time_model_factory
        self.processes: Dict[str, process.PROCESS_UNION] = {}

    def create_processes(self, adapter: production_system_data.ProductionSystemData):
        """
        Creates process objects based on the given adapter.

        Args:
            adapter (adapter.ProductionSystemAdapter): Adapter that contains the process data.
        """
        for process_data in adapter.process_data:
            self.add_processes(process_data, adapter)

    def add_processes(
        self,
        process_data: processes_data.PROCESS_DATA_UNION,
        adapter: production_system_data.ProductionSystemData,
    ):
        values = {"data": process_data}
        if not (
            isinstance(process_data, processes_data.CompoundProcessData)
            or isinstance(process_data, processes_data.RequiredCapabilityProcessData)
            or isinstance(process_data, processes_data.ProcessModelData)
        ):
            time_model = self.time_model_factory.get_time_model(
                process_data.time_model_id
            )
            values.update({"time_model": time_model})
        else:
            values.update({"time_model": None})
        if isinstance(process_data, processes_data.TransportProcessData):
            if process_data.loading_time_model_id is not None:
                values.update(
                    {
                        "loading_time_model": self.time_model_factory.get_time_model(
                            process_data.loading_time_model_id
                        )
                    }
                )
            if process_data.unloading_time_model_id is not None:
                values.update(
                    {
                        "unloading_time_model": self.time_model_factory.get_time_model(
                            process_data.unloading_time_model_id
                        )
                    }
                )
        if isinstance(process_data, processes_data.CompoundProcessData):
            contained_processes_data = [
                other_process_data
                for other_process_data in adapter.process_data
                if other_process_data.ID in process_data.process_ids
            ]
            values.update({"contained_processes_data": contained_processes_data})
        if isinstance(process_data, processes_data.LinkTransportProcessData):
            values.update({"links": [[]]})
        if isinstance(process_data, processes_data.ReworkProcessData):
            # TODO: think about getting here the processes and not only ids...
            values.update({"reworked_process_ids": process_data.reworked_process_ids})
            values.update({"blocking": process_data.blocking})
        if isinstance(process_data, (processes_data.ProcessModelData)):
            contained_processes = [self.processes[process_id] for process_id in process_data.adjacency_matrix.keys()]
            values.update({"contained_processes": contained_processes})

        process_class = PROCESS_MAP.get(process_data.type)
        if process_class is None:
            raise ValueError(f"Unknown process type: {process_data.type}")
        new_process = process_class(**values)
        self.processes[process_data.ID] = new_process

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
            if ID in self.processes:
                processes.append(self.processes[ID])
            else:
                raise ValueError(f"Process with ID {ID} not found")
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
        if ID in self.processes:
            return self.processes[ID]
        else:
            raise ValueError(f"Process with ID {ID} not found")


from prodsys.simulation import process
