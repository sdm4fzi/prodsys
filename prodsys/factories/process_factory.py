from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from pydantic import BaseModel, TypeAdapter

from prodsys.factories import time_model_factory
from prodsys.models import processes_data

if TYPE_CHECKING:
    from prodsys.adapters import adapter
    from prodsys.simulation import process


class ProcessFactory(BaseModel):
    """
    Factory class that creates and stores `prodsys.simulation` process objects based on the given process data according to `prodsys.models.processes_data.PROCESS_UNION`.

    Args:
        time_model_factory (time_model_factory.TimeModelFactory): Factory that creates time model objects.
        processes (List[process.PROCESS_UNION], optional): List of process objects. Defaults to [] and is filled by the `create_processes` method.
    """

    time_model_factory: time_model_factory.TimeModelFactory
    processes: List[process.PROCESS_UNION] = []

    def create_processes(self, adapter: adapter.ProductionSystemAdapter):
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
        adapter: adapter.ProductionSystemAdapter,
    ):
        values = {"process_data": process_data}
        if not (
            isinstance(process_data, processes_data.CompoundProcessData)
            or isinstance(process_data, processes_data.RequiredCapabilityProcessData)
        ):
            time_model = self.time_model_factory.get_time_model(
                process_data.time_model_id
            )
            values.update({"time_model": time_model})
        else:
            values.update({"time_model": None})
        if "failure_rate" in process_data:
            # TODO: fix this in simulation process to use parameter of process data
            values.update({"failure_rate": process_data.failure_rate})
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
            self.processes.append(
                TypeAdapter(process.LinkTransportProcess).validate_python(values)
            )
        elif isinstance(process_data, processes_data.ReworkProcessData):
            # TODO: think about getting here the processes and not only ids...
            values.update({"reworked_process_ids": process_data.reworked_process_ids})
            # TODO: fix this in simulation process to use parameter of process data
            values.update({"blocking": process_data.blocking})
            self.processes.append(
                TypeAdapter(process.ReworkProcess).validate_python(values)
            )
        else:
            self.processes.append(
                TypeAdapter(process.PROCESS_UNION).validate_python(values)
            )

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


from prodsys.simulation import process
