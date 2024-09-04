from __future__ import annotations

from hashlib import md5
from typing import TYPE_CHECKING, Union, List, Dict

from pydantic import root_validator

from prodsys.models.core_asset import CoreAsset
from prodsys.models import source_data

if TYPE_CHECKING:
    from prodsys.adapters.adapter import ProductionSystemAdapter


class AuxiliaryData(CoreAsset):
    """
    Class that represents auxiliary components required to process or transport a product by a resource..

    Some examples are workpiece carriers or tools.

    Args:
        ID (str): ID of the auxiliary component.
        description (str): Description of the auxiliary component.
        router (str): Router of the auxiliary component.
        transport_process (str): Transport process of the auxiliary component.
        storage_queues (List[str], optional): List of storage queues where the auxiliary component is stored between usages. Defaults to [].
        initial_quantity_in_queues (List[int], optional): List of initial quantities in the storage queues, in sequence of the storage queues. Defaults to [].
        relevant_processes (List[str], optional): List of relevant processes where the auxiliary component is needed. Defaults to [], meaning all processes.
        relevant_transport_processes (List[str], optional): List of relevant transport processes where the auxiliary component is needed. Defaults to [], meaning all processes.
    """
    auxiliary_type: str
    transport_process: str
    storages: List[str]
    initial_quantity_in_stores: List[int]
    relevant_processes: List[str] = []
    relevant_transport_processes: List[str] = []

    @root_validator(pre=True)
    def check_processes(cls, values):
        if "auxiliary_type" in values and values["auxiliary_type"]:
            values["ID"] = values["auxiliary_type"]
        else:
            values["auxiliary_type"] = values["ID"]
        return values

    def hash(self, adapter: ProductionSystemAdapter) -> str:
        """
        Function to hash the auxiliary component.

        Returns:
            str: Hash of the auxiliary component.
        """
        transport_processes_hash = ""
        storages_hashes = []
        relevant_processes_hashes = []
        relevant_transport_processes_hashes = []

        for queue in adapter.queue_data:
            if queue.ID in self.storages:
                storages_hashes.append(queue.hash())
        for process in adapter.process_data:
            if process.ID in self.relevant_processes:
                relevant_processes_hashes.append(process.hash(adapter))
            if process.ID in self.relevant_transport_processes:
                relevant_transport_processes_hashes.append(process.hash(adapter))
            if process.ID == self.transport_process:
                transport_processes_hash = process.hash(adapter)
        
        return md5("".join([*map(str, [self.auxiliary_type, self.initial_quantity_in_stores, transport_processes_hash, *storages_hashes, *self.initial_quantity_in_stores, *relevant_processes_hashes, *relevant_transport_processes_hashes])]).encode("utf-8")).hexdigest()