from typing import Any, Dict

import math
import scipy.stats
import datetime
import time

from pydantic import BaseModel
from prodsim import adapters
from prodsim.data_structures import resource_data, processes_data

import gurobipy as gp
from gurobipy import GRB


def get_modul_counts(adapter: adapters.Adapter) -> Dict[str, int]:
    modul_count_dict = {}
    for resource in adapter.resource_data:
        if not isinstance(resource, resource_data.ProductionResourceData):
            continue
        for process in resource.processes:
            if not process in modul_count_dict.keys():
                modul_count_dict[process] = 0
            modul_count_dict[process] += 1

    return modul_count_dict


class MathOptimizer(BaseModel):
    adapter: adapters.Adapter
    scenario_dict: Dict[str, str]
    model: Any = gp.Model("MILP_Rekonfiguration")

    def cost_module(self, x: int, Modul: str) -> int:
        module_cost = self.scenario_dict["costs"]["process_module"]
        return module_cost * (x - get_modul_counts(self.adapter)[Modul])

    def set_optimization_parameters(
        self,
    ):
        product_names = [material.ID for material in self.adapter.material_data]

    def set_variables(
        self,
    ):
        x = self.get_workpiece_index_variable()
        process_modules, stations = self.get_process_modules_and_stations()
        z = self.model.addVars(process_modules, stations, vtype=GRB.BINARY, name="z")
        s = self.model.addVars(stations, vtype=GRB.BINARY, name = "s")
        a = self.model.addVars(stations, vtype=GRB.CONTINUOUS, name = "a")
        v = self.model.addVars(stations, vtype=GRB.CONTINUOUS, name = "v")
        t = self.model.addVars(process_modules, vtype=GRB.INTEGER, name = "t")

    def get_workpiece_index_variable(self) -> dict:
        x = {}
        for product_type in self.adapter.material_data:
            work_piece_count = self.scenario_dict["target"][product_type.ID]
            for work_piece_index in range(work_piece_count):
                for step in product_type.processes:
                    for station in range(
                        self.scenario_dict["constraints"]["max_num_machines"]
                    ):
                        x[
                            product_type.ID, work_piece_index, step, station
                        ] = self.model.addVar(
                            vtype=GRB.BINARY,
                            name="x[{},{},{},{}]".format(
                                product_type.ID, work_piece_index, step, station
                            ),
                        )
        return x

    def get_process_modules_and_stations(self):
        process_modules = [
            process.ID
            for process in self.adapter.process_data
            if isinstance(process, processes_data.ProductionProcessData)
        ]
        stations = [
            station
            for station in range(self.scenario_dict["constraints"]["max_num_machines"])
        ]
        return process_modules, stations

    def set_constraints(
        self,
    ):
        pass

    def set_objective_function(
        self,
    ):
        pass

    def optimize(
        self,
    ):
        pass

    def save_model(
        self,
    ):
        pass

    def save_result_to_adapter(
        self,
    ):
        pass
