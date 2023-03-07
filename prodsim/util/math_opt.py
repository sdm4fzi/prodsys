from typing import Any, Dict, Tuple, List

import math
import scipy.stats
import datetime
import time
from copy import deepcopy

from pydantic import BaseModel
from prodsim import adapters
from prodsim.data_structures import (
    resource_data,
    processes_data,
    state_data,
    time_model_data,
)
from prodsim.util import optimization_util

import gurobipy as gp
from gurobipy import GRB

import numpy as np


def get_modul_counts(adapter: adapters.Adapter) -> Dict[str, int]:
    modul_count_dict = {}
    # Fall Prozessmodul noch nicht vorhanden fehlt
    for process in adapter.process_data:
        if isinstance(process, processes_data.ProductionProcessData):
            modul_count_dict[process.ID] = 0
    for resource in adapter.resource_data:
        if not isinstance(resource, resource_data.ProductionResourceData):
            continue
        for process in resource.processes:
            modul_count_dict[process] += 1

    return modul_count_dict


class MathOptimizer(BaseModel):
    adapter: adapters.Adapter

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
        module_cost = self.adapter.scenario_data.info.process_module_cost
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
            x[product_type.ID] = {}
            work_piece_count = (
                self.adapter.scenario_data.constraints.target_material_count[
                    product_type.ID
                ]
            )
            for work_piece_index in range(work_piece_count):
                x[product_type.ID][work_piece_index] = {}
                for step in product_type.processes:
                    x[product_type.ID][work_piece_index][step] = {}
                    for station in range(
                        self.adapter.scenario_data.constraints.max_num_machines
                    ):
                        x[product_type.ID][work_piece_index][step][
                            station
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
            for station in range(
                self.adapter.scenario_data.constraints.max_num_machines
            )
        ]
        return process_modules, stations

    def get_opening_cost_of_stations(self):
        opening_cost = {}
        _, stations = self.get_process_modules_and_stations()
        num_previous_machines = len(adapters.get_machines(self.adapter))
        for counter, station in enumerate(stations):
            if counter < num_previous_machines:
                opening_cost[station] = 0
            else:
                opening_cost[station] = self.adapter.scenario_data.info.machine_cost
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
                self.v[station] * self.adapter.scenario_data.info.breakdown_cost
                for station in stations
            )
        )
        self.model.setObjective(objective, GRB.MINIMIZE)

    def set_constraints(
        self,
    ):
        self.check_available_station_for_workpieces()
        self.check_available_station()
        self.check_extended_time_per_station()
        self.check_cost_of_modules()
        self.check_maximum_breakdown_time()

    def check_available_station_for_workpieces(self):
        for product, workpieces in self.x.items():
            for workpiece, process_steps in workpieces.items():
                for process_step, stations in process_steps.items():
                    for station, variable in stations.items():
                        self.model.addConstr(
                            variable - self.s[station] <= 0,
                            "für_{}_Werkstück_{}_{}_durchgeführt_an_Station_{}".format(
                                product, workpiece, process_step, station
                            ),
                        )

    def check_available_station_for_workpieces(self):
        for product, workpieces in self.x.items():
            for workpiece, process_steps in workpieces.items():
                for process_step, stations in process_steps.items():
                    self.model.addConstr(
                        sum(
                            self.x[product][workpiece][process_step][station]
                            for station in stations.keys()
                        )
                        == 1,
                        "für_{}_Werkstück_{}_wird_{}_durchgeführt".format(
                            product, workpiece, process_step
                        ),
                    )

    def check_available_station(self):
        for product, workpieces in self.x.items():
            for workpiece, process_steps in workpieces.items():
                for process_step, stations in process_steps.items():
                    for station in stations.keys():
                        self.model.addConstr(
                            (
                                self.x[product][workpiece][process_step][station]
                                - self.z[process_step, station]
                                <= 0
                            ),
                            "für_{}_Werkstück_{}_{}_vorhanden_an_Station_{}".format(
                                product, workpiece, process_step, station
                            ),
                        )

    def get_state_with_id(self, state_id: str) -> state_data.BreakDownStateData:
        return [
            state for state in self.adapter.state_data if state.ID == state_id
        ].pop()

    def get_expected_time_of_time_model_with_id(
        self, time_model_id: str
    ) -> time_model_data:
        return (
            [
                time_model
                for time_model in self.adapter.time_model_data
                if time_model.ID == time_model_id
            ]
            .pop()
            .parameters[0]
        )

    def get_breakdown_values(self):

        # Berechnung der Erwartungswerte (durchschnittliche Zeit bis zum Ausfall) E(x)=1/λ
        machine_breakdown_state = self.get_state_with_id(
            optimization_util.BreakdownStateNamingConventino.MACHINE_BREAKDOWN_STATE
        )
        process_module_breakdown_state = self.get_state_with_id(
            optimization_util.BreakdownStateNamingConventino.PROCESS_MODULE_BREAKDOWN_STATE
        )

        MTTF_machine = self.get_expected_time_of_time_model_with_id(
            machine_breakdown_state.time_model_id
        )
        MTTR_machine = self.get_expected_time_of_time_model_with_id(
            machine_breakdown_state.repair_time_model_id
        )
        MTTF_process_module = self.get_expected_time_of_time_model_with_id(
            process_module_breakdown_state.time_model_id
        )
        MTTR_process_module = self.get_expected_time_of_time_model_with_id(
            process_module_breakdown_state.repair_time_model_id
        )

        # Berechnung der erwarteten Anzahl an Fehlern und Zeitdauern der Fehler
        BZ = self.adapter.scenario_data.info.time_range
        machine_breakdown_count = BZ / MTTF_machine
        machine_breakdown_time = MTTR_machine

        process_modules, stations = self.get_process_modules_and_stations()

        module_breakdown_count = {
            module: BZ / MTTF_process_module for module in process_modules
        }

        module_breakdown_time = {
            module: MTTR_process_module for module in process_modules
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
        for station in range(self.adapter.scenario_data.constraints.max_num_machines):
            self.model.addConstr(
                (
                    (
                        (
                            self.s[station]
                            * machine_breakdown_count
                            * machine_breakdown_time
                        )
                        + sum(
                            self.z[module, station]
                            * module_breakdown_count[module]
                            * module_breakdown_time[module]
                            for module in module_breakdown_count
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
                process = next(
                    filter(
                        lambda process: process.ID == step, self.adapter.process_data
                    )
                )
                time_model = next(
                    filter(
                        lambda time_model: time_model.ID == process.time_model_id,
                        self.adapter.time_model_data,
                    )
                )
                # Adjust processing times with safety factor (0,85-Quantil of the normal distribution)
                quantil = scipy.stats.norm.ppf(0.85, loc=0, scale=1)
                processing_times_per_product_and_step[product.ID][
                    step
                ] = time_model.parameters[0] + (time_model.parameters[1] * quantil)
        return processing_times_per_product_and_step

    def check_extended_time_per_station(self):
        BZ = self.adapter.scenario_data.info.time_range

        for station in range(self.adapter.scenario_data.constraints.max_num_machines):
            self.model.addConstr(
                (
                    (
                        gp.quicksum(
                            self.processing_times_per_product_and_step[product][step]
                            * self.x[product][workpiece][step][station]
                            for product, workpieces in self.x.items()
                            for workpiece, process_steps in workpieces.items()
                            for step in process_steps.keys()
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
                - self.adapter.scenario_data.info.maximum_breakdown_time
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
        self.set_objective_function()

        # Optimierung
        stopt = datetime.datetime.now()
        self.model.optimize()
        end = datetime.datetime.now()
        print(end - stopt)

        status = self.model.Status
        if status == GRB.UNBOUNDED:
            print("The model cannot be solved because it is unbounded")
        if status == GRB.OPTIMAL:
            print("The optimal objective is %g" % self.model.ObjVal)
        if status != GRB.INF_OR_UNBD and status != GRB.INFEASIBLE:
            print("Optimization was stopped with status %d" % status)

        elapsed_time = end - st
        print("Execution time:", elapsed_time, "seconds")
        self.model.write("MILP.lp")
        # TODO: store results for later export or postprocessing
        for entry in self.model.__dict__:
            print(entry)

    def save_model(
        self,
    ):
        pass
        # self.adapters.resource_data.append(resource_data.ProductionResourceData())

    def save_result_to_adapter(
        self,
    ):
        # TODO: get most relevant results / solutions from optimization model
        results = []

        for counter, result in enumerate(results):
            new_adapter = self.adapter.copy(deep=True)
            new_adapter.resource_data = [
                resource
                for resource in self.adapter.resource
                if not isinstance(resource, resource_data.ProductionResourceData)
            ]
            possible_positions = deepcopy(self.adapter.scenario_data.options.positions)

            # Retrieve from result the resource data that specifies the used process modules
            resources_data = []
            for station in self.s:
                if station.X == 1:
                    resources_data.append(station)

            for resource_counter, resource in enumerate(resources_data):
                processes = []  # Ids for used process modules on this machine
                modules = self.get_process_modules_and_stations()[0]
                for module in modules:
                    if self.z[module, resource] == 1:
                        processes.append(module)

                states = [
                    optimization_util.BreakdownStateNamingConventino.MACHINE_BREAKDOWN_STATE
                ] + len(processes) * [
                    optimization_util.BreakdownStateNamingConventino.PROCESS_MODULE_BREAKDOWN_STATE
                ]
                location = np.random.choice(possible_positions)
                possible_positions.remove(location)
                new_resource = resource_data.ProductionResourceData(
                    ID="M" + str(resource_counter),
                    description="",
                    capacity=1,
                    location=location,
                    controller="SimpleController",
                    control_policy="FIFO",
                    processes=processes,
                    process_capacity=None,
                    states=states,
                )
                new_adapter.resource_data.append(new_resource)
            new_adapter.write_data(f"data/math_opt_solution_{counter}.json")
