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
    scenario_dict: Dict[str, Any]

    model: Any = None
    x: Any = None
    z: Any = None
    s: Any = None
    a: Any = None
    v: Any = None
    t: Any = None

    processing_times_per_product_and_step: dict = None

    class Config:
        arbitrary_types_allowed = True

    def cost_module(self, x: int, Modul: str) -> int:
        module_cost = self.scenario_dict["costs"]["process_module"]
        return module_cost * (x - get_modul_counts(self.adapter)[Modul])
        
    def set_variables(
        self,
    ):  
        self.processing_times_per_product_and_step = (
            self.get_processing_times_per_product_and_step()
        )
        self.x = self.get_workpiece_index_variable()
        process_modules, stations = self.get_process_modules_and_stations()
        self.z = self.model.addVars(
            process_modules, stations, vtype=GRB.BINARY, name="z"
        )
        self.s = self.model.addVars(stations, vtype=GRB.BINARY, name="s")
        self.a = self.model.addVars(stations, vtype=GRB.CONTINUOUS, name="a")
        self.v = self.model.addVars(stations, vtype=GRB.CONTINUOUS, name="v")
        self.t = self.model.addVars(process_modules, vtype=GRB.INTEGER, name="t")

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
    
    def get_opening_cost_of_stations(self):
        opening_cost = {}
        _, stations = self.get_process_modules_and_stations()
        num_previous_machines = len(adapters.get_machines(self.adapter))
        for counter, station in enumerate(stations):
            if counter <= num_previous_machines:
                opening_cost[station] = 0
            else:
                opening_cost[station] = self.scenario_dict["costs"]["machine"]
        return opening_cost


    def set_objective_function(
        self,
    ):
        process_modules, stations = self.get_process_modules_and_stations()
        opening_costs = self.get_opening_cost_of_stations()
        objective = (
            sum(self.t[modul] for modul in process_modules)
            + sum(opening_costs[station] * self.s[station] for station in stations)
            + sum(
                self.v[station] * self.scenario_dict["costs"]["breakdown_cost"]
                for station in stations
            )
        )
        self.model.setObjective(objective, GRB.MINIMIZE)

    def set_constraints(
        self,
    ):
        self.check_available_station()
        self.check_available_station_for_workpieces()
        self.check_available_station()
        self.check_extended_time_per_station()
        self.check_extended_time_per_station()
        self.check_cost_of_modules()
        self.check_maximum_breakdown_time()

    def check_available_station(self):
        for product in self.x.keys():
            for workpiece in product.keys():
                for step in workpiece.keys():
                    for station, variable in step.items():
                        self.model.addConstr(
                            variable - self.s[station] <= 0,
                            "für_{}_{}_{}_durchgeführt_an_{}".format(
                                product, workpiece, step, station
                            ),
                        )

    def check_available_station_for_workpieces(self):
        for product in self.x.keys():
            for workpiece in product.keys():
                for process_step in workpiece.keys():
                    self.model.addConstr(
                        sum(
                            self.x[product, workpiece, process_step, Station]
                            for Station in process_step.keys()
                        )
                        == 1,
                        "für_{}_{}_wird_{}_durchgeführt".format(
                            product, workpiece, process_step
                        ),
                    )

    def check_available_station(self):
        for product in self.x.keys():
            for workpiece in product.keys():
                for process_step in workpiece.keys():
                    for station in process_step.keys():
                        self.model.addConstr(
                            (
                                self.x[product, workpiece, process_step, station]
                                - self.z[process_step, station]
                                <= 0
                            ),
                            "für_{}_{}_{}_vorhanden_an_{}".format(
                                product, workpiece, process_step, station
                            ),
                        )

    # TODO: move into adapter!
    def get_breakdown_values(self):
        # Definition der Ausfallraten je Maschine / Modul
        # Ausfallrate Maschine
        p = 0.0003
        # Ausfallrate Module λ
        λ_M1 = 0.0002
        λ_M2 = 0.0002
        λ_M3 = 0.0002
        λ_M4 = 0.0002
        λ_M5 = 0.0002
        λ_M6 = 0.0002

        # Berechnung der Erwartungswerte (durchschnittliche Zeit bis zum Ausfall) E(x)=1/λ
        Ex_Maschine = 1 / p
        Ex_M1 = 1 / λ_M1
        Ex_M2 = 1 / λ_M2
        Ex_M3 = 1 / λ_M3
        Ex_M4 = 1 / λ_M4
        Ex_M5 = 1 / λ_M5
        Ex_M6 = 1 / λ_M6

        # Berechnung der erwarteten Anzahl an Fehlern = betrachteter Zeitraum / E(x)
        BZ = self.scenario_dict["time_range"]
        machine_breakdown_count = BZ / Ex_Maschine
        module_breakdown_count = {
            "Modul_1": BZ / Ex_M1,
            "Modul_2": BZ / Ex_M2,
            "Modul_3": BZ / Ex_M3,
            "Modul_4": BZ / Ex_M4,
            "Modul_5": BZ / Ex_M5,
            "Modul_6": BZ / Ex_M6,
        }

        # Definition der durchschnittlichen Ausfalldauer einer Maschine / eines Moduls
        machine_breakdown_time = 15
        module_breakdown_time = {
            "Modul_1": 10,
            "Modul_2": 10,
            "Modul_3": 10,
            "Modul_4": 10,
            "Modul_5": 10,
            "Modul_6": 10,
        }

        return (
            machine_breakdown_count,
            module_breakdown_count,
            machine_breakdown_time,
            module_breakdown_time,
        )

    def check_extended_time_per_station(self):
        (
            machine_breakdown_count,
            module_breakdown_count,
            machine_breakdown_time,
            module_breakdown_time,
        ) = self.get_breakdown_values()
        for station in range(self.scenario_dict["constraints"]["max_num_machines"]):
            self.model.addConstr(
                (
                    (
                        (
                            self.s[station]
                            * machine_breakdown_count
                            * machine_breakdown_time
                        )
                        + sum(
                            self.z[Modul, station]
                            * module_breakdown_count[Modul]
                            * module_breakdown_time[Modul]
                            for Modul in module_breakdown_count
                        )
                    )
                    == self.a[station]
                ),
                "Berechnung_der_Ausfallzeit_von_{}".format(station),
            )

    def get_processing_times_per_product_and_step(self):
        processing_times_per_product_and_step = {}
        for product in self.adapter.material_data:
            processing_times_per_product_and_step[product.ID] = {}
            for step in product.processes:
                process = next(filter(
                    lambda process: process.ID == step, self.adapter.process_data
                ))
                time_model = next(filter(
                    lambda time_model: time_model.ID == process.time_model_id,
                    self.adapter.time_model_data,
                ))

                processing_times_per_product_and_step[product.ID][
                    step
                ] = time_model.parameters[0]
        return processing_times_per_product_and_step

    def check_extended_time_per_station(self):
        BZ = self.scenario_dict["time_range"]

        for station in range(self.scenario_dict["constraints"]["max_num_machines"]):
            self.model.addConstr(
                (
                    (
                        gp.quicksum(
                            self.processing_times_per_product_and_step[product][step]
                            * self.x[product, workpiece, step, station]
                            for product in self.x.keys()
                            for workpiece in product.keys()
                            for step in workpiece.keys()
                        )
                    )
                    + self.a[station]
                    - BZ
                    <= 0
                ),
                "Berechnung_der_überschrittenen_Zeit_an_{}".format(station),
            )

    def check_cost_of_modules(self):
        process_modules, stations = self.get_process_modules_and_stations()
        for module in process_modules:
            self.model.addConstr(
                (
                    self.cost_module(
                        sum(self.z[module, station] for station in stations), module
                    )
                    - self.t[module]
                    <= 0
                ),
                "Sicherstellen_Maximum_{}".format(module),
            )

    def check_maximum_breakdown_time(self):
        _, stations = self.get_process_modules_and_stations()
        self.model.addConstr(
            (
                sum(self.v[Station] for Station in stations)
                - self.scenario_dict["maximum_breakdown_time"]
                <= 0
            ),
            "Maximale_Ausfallzeit_einhalten",
        )

    def optimize(
        self,
    ):  
        st = datetime.datetime.now()
        self.model: Any = gp.Model("MILP_Rekonfiguration")


        self.set_variables()
        self.set_constraints()

        # Optimierung
        stopt = datetime.datetime.now()
        self.model.optimize()
        end = datetime.datetime.now()
        print(end-stopt)

        status = self.model.Status
        if status == GRB.UNBOUNDED:
            print('The model cannot be solved because it is unbounded')
        if status == GRB.OPTIMAL:
            print('The optimal objective is %g' % self.model.ObjVal)
        if status != GRB.INF_OR_UNBD and status != GRB.INFEASIBLE:
            print('Optimization was stopped with status %d' % status)

        elapsed_time = end - st
        print('Execution time:', elapsed_time, 'seconds')

        # TODO: store results for later export or postprocessing


    def save_model(
        self,
    ):
        pass
        # self.adapters.resource_data.append(resource_data.ProductionResourceData())

    def save_result_to_adapter(
        self,
    ):
        pass
