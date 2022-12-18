from typing import Dict, Union
from dataclasses import dataclass


import pandas as pd

from .. import loader


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

@dataclass
class ProcessTime:
    machineDurationGroup: str
    taskDurationGroup: str
    duration: float

@dataclass
class FlexisData:
    ApplicationName: pd.DataFrame
    Capability: pd.DataFrame
    Customer: pd.DataFrame
    Product: pd.DataFrame
    OrderType: pd.DataFrame
    JobType: pd.DataFrame
    Order: pd.DataFrame
    Location: pd.DataFrame
    Machine: pd.DataFrame
    TaskType: pd.DataFrame
    WorkPlan: pd.DataFrame
    SetupTime: pd.DataFrame
    ProcessTime: pd.DataFrame
    TransitionTime: pd.DataFrame
    CalendarParameter: pd.DataFrame
    DayPattern: pd.DataFrame
    Shift: pd.DataFrame
    NonworkingDay: pd.DataFrame
    Constraint: pd.DataFrame
    LinkType: pd.DataFrame
    Link: pd.DataFrame

class FlexisAdapter(loader.Loader):

    def read_data(self, file_path: str):

        # read excel file
        xls = pd.ExcelFile(file_path)
        df_machine = pd.read_excel(xls, "Machine")
        input_data = {}
        for sheet_name in xls.sheet_names:
            input_data[sheet_name] = pd.read_excel(xls, sheet_name)
        
        data = FlexisData(**input_data)

    def write_data(self, file_path: str):
        pass

