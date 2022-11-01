from typing import Dict, Union
import json

from . import loader


def get_minimum_simjson_structure() -> Dict[str, Union[str, list, dict]]:
    return {
        "alternatives": [],
        "mainVersion": "",
        "createdWithVersion": "",
        "name": "",
        "settings": {},
    }


def set_simjson_default_values(sim_json: dict):
    sim_json["createdWithVersion"] = "2.3.0-pre.2"
    sim_json["mainVersion"] = "0.1.2"
    sim_json["settings"]["shiftCalendars"] = []
    sim_json["name"] = "wbk_test"


def get_default_simjson() -> Dict[str, Union[str, list, dict]]:
    sim_json = get_minimum_simjson_structure()
    set_simjson_default_values(sim_json)
    return sim_json


def get_default_variant(variant_name: str) -> dict:
    model = {
        "class": "GraphLinksModel",
        "copiesArrays": True,
        "copiesArrayObjects": True,
        "linkFromPortIdProperty": "fromPort",
        "linkToPortIdProperty": "toPort",
        "nodeDataArray": [],
        "linkDataArray": [],
    }

    variant = {
        "name": variant_name,
        "modificationTime": "2022-11-01T16:56:03.569Z",
        "model": model,
    }

    return variant


class SimJSONExorter:
    def __init__(self, filepath: str):
        self.filepath: str = filepath
        self.simjson_file: dict = dict()
        try:
            self.read_existing_simjson()
        except:
            self.create_simjson_file()

    def read_existing_simjson(self):
        with open(self.filepath, "r", encoding="utf-8") as json_file:
            self.simjson_file = json.load(json_file)

    def save_simjson_file(self):
        with open(self.filepath, "w", encoding="utf-8") as json_file:
            json.dump(self.simjson_file, json_file)

    def create_simjson_file(self):
        self.simjson_file = get_default_simjson()
        self.save_simjson_file()

    def get_machine_node(self) -> dict:
        node_dict = {
            "category": "item",
            "class": "ca3sarCell", # gleiches noch für "drain", "source", "agvpool", ("virtualcell")
            "parameters": [
                {"class": "v_tiProcTime", "type": "time", "value": 60}, # process time
                {"class": "v_rAvailability", "type": "number", "value": 98.5}, # availability
                {"class": "v_tiMTTR", "type": "time", "value": 300}, # MMTR
                {"class": "comment", "type": "string"}, # comment
            ],
            "key": 0, # key to identify object --> index from 0 upwards
            "loc": "-50 250",
            "nodeName": "Ca3sar_Zelle", # Id of machine
            "phoNames": []
        }
        return node_dict
    
    def get_transport_node(self) -> dict:
        return {}
    
    def get_source_node(self) -> dict:
        return {}
    
    def get_drain_node(self) -> dict:
        return {}
    
    def get_link(self) -> dict:
        link_dict = {
            "category": "item",
            "from": -1, # ID of the source node
            "to": -4, # ID of the target node
            "fromPort": "R",
            "toPort": "L",
            "class": "connection",
            "routingBehaviour": "direct", # direct as deault
            "points": [-273, -250, -263, -250, -87, -250, -77, -250] # not required
          }
        
        return link_dict

    def add_variant_to_simjson(self, variant_name: str, loader: loader.CustomLoader):
        """Returns a simjson file"""
        variant = get_default_variant(variant_name=variant_name)
