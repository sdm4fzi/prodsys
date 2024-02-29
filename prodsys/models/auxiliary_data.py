from __future__ import annotations

from typing import Union, List, Dict

from pydantic import root_validator

from prodsys.models.core_asset import CoreAsset


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
    #router: str
    transport_process: str
    storages: List[str]
    initial_quantity_in_stores: List[int]
    relevant_processes: List[str] = []
    relevant_transport_processes: List[str] = []
