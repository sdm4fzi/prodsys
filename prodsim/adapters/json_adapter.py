from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import parse_obj_as, BaseModel

from prodsim.adapters import adapter

from prodsim.data_structures import (
    queue_data,
    resource_data,
    time_model_data,
    state_data,
    processes_data,
    material_data,
    sink_data,
    source_data,
)

def load_json(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as json_file:
        data = json.load(json_file)
    return data

class JsonAdapter(adapter.Adapter):
    def read_data(self, file_path: str, scenario_file_path: Optional[str] = None):
        data = load_json(file_path=file_path)
        self.seed = data["seed"]
        self.time_model_data = self.create_objects_from_configuration_data(
            data["time_models"], time_model_data.TIME_MODEL_DATA
        )
        self.state_data = self.create_objects_from_configuration_data(
            data["states"], state_data.STATE_DATA_UNION
        )
        self.process_data = self.create_objects_from_configuration_data(
            data["processes"], processes_data.PROCESS_DATA_UNION
        )

        self.queue_data = self.create_objects_from_configuration_data(data["queues"], queue_data.QueueData)
        self.resource_data = self.create_objects_from_configuration_data(data["resources"], resource_data.RESOURCE_DATA_UNION)
        self.material_data = self.create_objects_from_configuration_data(data["materials"], material_data.MaterialData)
        self.sink_data = self.create_objects_from_configuration_data(data["sinks"], sink_data.SinkData)
        self.source_data = self.create_objects_from_configuration_data(data["sources"], source_data.SourceData)
        if scenario_file_path:
            self.read_scenario(scenario_file_path)

    def create_typed_object_from_configuration_data(
        self, configuration_data: Dict[str, Any], type
    ):
        objects = []
        for cls_name, items in configuration_data.items():
            for values in items.values():
                values.update({"type": cls_name})
                objects.append(parse_obj_as(type, values))
        return objects
    
    def create_objects_from_configuration_data(
        self, configuration_data: Dict[str, Any], type
    ):  
        objects = []
        for values in configuration_data.values():
            objects.append(parse_obj_as(type, values))
        return objects

    def write_data(self, file_path: str):
        data = self.get_dict_object_of_adapter()
        with open(file_path, "w") as json_file:
            json.dump(data, json_file)

    def get_dict_object_of_adapter(self) -> dict:
        data = {
                "seed": self.seed,
                "time_models": self.get_dict_of_list_objects(self.time_model_data),
                "states": self.get_dict_of_list_objects(self.state_data),
                "processes": self.get_dict_of_list_objects(self.process_data),
                "queues": self.get_dict_of_list_objects(self.queue_data),
                "resources": self.get_dict_of_list_objects(self.resource_data),
                "materials": self.get_dict_of_list_objects(self.material_data),
                "sinks": self.get_dict_of_list_objects(self.sink_data),
                "sources": self.get_dict_of_list_objects(self.source_data)
        }
        return data
    
    def write_scenario_data(self, file_path: str) -> None:
        data = self.scenario_data.dict()
        with open(file_path, "w") as json_file:
            json.dump(data, json_file)

    def get_dict_of_list_objects(self, values: List[BaseModel]) -> dict:
        return {counter: data.dict() for counter, data in enumerate(values)}