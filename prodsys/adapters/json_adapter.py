from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import parse_obj_as, BaseModel
from warnings import warn


from prodsys.adapters import adapter

from prodsys.models import (
    product_data,
    queue_data,
    resource_data,
    node_data,
    time_model_data,
    state_data,
    processes_data,
    sink_data,
    source_data,
)

def load_json(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as json_file:
        data = json.load(json_file)
    return data

class JsonProductionSystemAdapter(adapter.ProductionSystemAdapter):
    """
    JsonProductionSystemAdapter is a class that implements the abstract class ProductionSystemAdapter and allows to read and write data from and to a json file.

    Args:
        ID (str, optional): ID of the production system. Defaults to "".
        seed (int, optional): Seed for the random number generator used in simulation. Defaults to 0.
        time_model_data (List[time_model_data.TIME_MODEL_DATA], optional): List of time models used by the entities in the production system. Defaults to [].
        state_data (List[state_data.STATE_DATA_UNION], optional): List of states used by the resources in the production system. Defaults to [].
        process_data (List[processes_data.PROCESS_DATA_UNION], optional): List of processes required by products and provided by resources in the production system. Defaults to [].
        queue_data (List[queue_data.QueueData], optional): List of queues used by the resources, sources and sinks in the production system. Defaults to [].
        resource_data (List[resource_data.RESOURCE_DATA_UNION], optional): List of resources in the production system. Defaults to [].
        node_data (List[resource_data.NodeData], optional): List of nodes in the production system. Defaults to [].
        product_data (List[product_data.ProductData], optional): List of products in the production system. Defaults to [].
        sink_data (List[sink_data.SinkData], optional): List of sinks in the production system. Defaults to [].
        source_data (List[source_data.SourceData], optional): List of sources in the production system. Defaults to [].
        scenario_data (Optional[scenario_data.ScenarioData], optional): Scenario data of the production system used for optimization. Defaults to None.
        valid_configuration (bool, optional): Indicates if the configuration is valid. Defaults to True.
        reconfiguration_cost (float, optional): Cost of reconfiguration in a optimization scenario. Defaults to 0.
    """

    def read_data_old(self, file_path: str, scenario_file_path: Optional[str] = None):
        """
        Reads the data from the given file path and scenario file path.

        Args:
            file_path (str): File path for the production system configuration
            scenario_file_path (Optional[str], optional): File path for the scenario data. Defaults to None.
        """
        warn("This method is deprecated. Use read_data instead.", DeprecationWarning)
        data = load_json(file_path=file_path)
        self.seed = data["seed"]
        self.time_model_data = self.create_objects_from_configuration_data_old(
            data["time_models"], time_model_data.TIME_MODEL_DATA
        )
        self.state_data = self.create_objects_from_configuration_data_old(
            data["states"], state_data.STATE_DATA_UNION
        )
        self.process_data = self.create_objects_from_configuration_data_old(
            data["processes"], processes_data.PROCESS_DATA_UNION
        )

        self.queue_data = self.create_objects_from_configuration_data_old(data["queues"], queue_data.QueueData)
        self.resource_data = self.create_objects_from_configuration_data_old(data["resources"], resource_data.RESOURCE_DATA_UNION)
        self.product_data = self.create_objects_from_configuration_data_old(data["products"], product_data.ProductData)
        self.node_data = self.create_objects_from_configuration_data(data["links"], node_data.NodeData)
        self.sink_data = self.create_objects_from_configuration_data_old(data["sinks"], sink_data.SinkData)
        self.source_data = self.create_objects_from_configuration_data_old(data["sources"], source_data.SourceData)
        if scenario_file_path:
            self.read_scenario(scenario_file_path)

    def read_data(self, file_path: str, scenario_file_path: Optional[str] = None):
        """
        Reads the data from the given file path and scenario file path.

        Args:
            file_path (str): File path for the production system configuration
            scenario_file_path (Optional[str], optional): File path for the scenario data. Defaults to None.
        """
        data = load_json(file_path=file_path)
        if "ID" in data:
            self.ID = data["ID"]
        if "seed" in data:
            self.seed = data["seed"]
        else:
            self.seed = 0
        self.time_model_data = self.create_objects_from_configuration_data(
            data["time_model_data"], time_model_data.TIME_MODEL_DATA
        )
        self.state_data = self.create_objects_from_configuration_data(
            data["state_data"], state_data.STATE_DATA_UNION
        )
        self.process_data = self.create_objects_from_configuration_data(
            data["process_data"], processes_data.PROCESS_DATA_UNION
        )
        self.queue_data = self.create_objects_from_configuration_data(data["queue_data"], queue_data.QueueData)
        self.resource_data = self.create_objects_from_configuration_data(data["resource_data"], resource_data.RESOURCE_DATA_UNION)
        self.product_data = self.create_objects_from_configuration_data(data["product_data"], product_data.ProductData)
        self.sink_data = self.create_objects_from_configuration_data(data["sink_data"], sink_data.SinkData)
        if "node_data" in data:
            self.node_data = self.create_objects_from_configuration_data(data["node_data"], node_data.NodeData)
        self.source_data = self.create_objects_from_configuration_data(data["source_data"], source_data.SourceData)
        if scenario_file_path:
            self.read_scenario(scenario_file_path)
    
    def create_objects_from_configuration_data_old(
        self, configuration_data: Dict[str, Any], type
    ):  
        warn("This method is deprecated. Use create_objects_from_configuration_data instead.", DeprecationWarning)
        objects = []
        for values in configuration_data.values():
            objects.append(parse_obj_as(type, values))
        return objects
    
    def create_objects_from_configuration_data(
        self, configuration_data: List[Any], type
    ):  
        objects = []
        for values in configuration_data:
            objects.append(parse_obj_as(type, values))
        return objects

    def write_data(self, file_path: str):
        """
        Writes the data to the given file path.

        Args:
            file_path (str): File path for the production system configuration
        """
        data = self.get_dict_object_of_adapter()
        with open(file_path, "w") as json_file:
            json.dump(data, json_file)

    def get_dict_object_of_adapter(self) -> dict:
        data = {
                "ID": self.ID,
                "seed": self.seed,
                "time_model_data": self.get_list_of_dict_objects(self.time_model_data),
                "state_data": self.get_list_of_dict_objects(self.state_data),
                "process_data": self.get_list_of_dict_objects(self.process_data),
                "node_data": self.get_list_of_dict_objects(self.node_data),
                "queue_data": self.get_list_of_dict_objects(self.queue_data),
                "resource_data": self.get_list_of_dict_objects(self.resource_data),
                "node_data": self.get_list_of_dict_objects(self.node_data),
                "product_data": self.get_list_of_dict_objects(self.product_data),
                "sink_data": self.get_list_of_dict_objects(self.sink_data),
                "source_data": self.get_list_of_dict_objects(self.source_data)
        }
        return data
    
    def write_scenario_data(self, file_path: str) -> None:
        """
        Writes the scenario data to the given file path.

        Args:
            file_path (str): File path for the scenario data.
        """
        data = self.scenario_data.dict()
        with open(file_path, "w") as json_file:
            json.dump(data, json_file)

    def get_list_of_dict_objects(self, values: List[BaseModel]) -> List[dict]:
        return  [data.dict() for data in values]