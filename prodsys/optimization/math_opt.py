from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from prodsys.optimization.optimizer import Optimizer
from prodsys.optimization.util import (
    check_breakdown_states_available,
    create_default_breakdown_states,
)
from uuid import uuid1
import scipy.stats
import datetime
from copy import deepcopy
import json
import random
import logging

logger = logging.getLogger(__name__)

from pydantic import BaseModel, ConfigDict
from prodsys import adapters
from prodsys.models import (
    resource_data,
    processes_data,
    state_data,
    time_model_data,
)
from prodsys.optimization import (
    adapter_manipulation,
    optimization,
    util as optimization_util,
)
from prodsys.util import util

import gurobipy as gp
from gurobipy import GRB


def adjust_number_of_transport_resources(
    adapter_object: adapters.ProductionSystemData, number_of_transport_resources: int
) -> None:
    """Adjusts the number of transport resources in the adapter object.

    Args:
        adapter_object (adapters.Adapter): Adapter object.
        number_of_transport_resources (int): Number of transport resources.
    """
    existing_transport_resource = adapter_object.resource_data[0]
    existing_transport_resource.ID = "TR0"
    for i in range(number_of_transport_resources - 1):
        new_transport_resource = existing_transport_resource.model_copy(deep=True)
        new_transport_resource.ID = f"TR{i + 1}"
        adapter_object.resource_data.append(new_transport_resource)


def get_modul_counts(adapter: adapters.ProductionSystemData) -> Dict[str, int]:
    modul_count_dict = {}
    # Fall Prozessmodul noch nicht vorhanden fehlt
    for process in adapter.process_data:
        if isinstance(process, processes_data.ProductionProcessData):
            modul_count_dict[process.ID] = 0
    for resource in adapter.resource_data:
        if not isinstance(resource, resource_data.ResourceData):
            continue
        for process in resource.process_ids:
            modul_count_dict[process] += 1

    return modul_count_dict


class MathOptimizer(BaseModel):
    """
    Mathematical optimizer for configuration planning of production systems. For mathetical optimization, only production capacity, cosidering the number of production resources and their processes. Here, only configuration cost can be optimized. However, the mathematical optimization set the expected number of produced products as a constraint, thus allowing for a target output.

    Args:
        adapter (adapters.ProductionSystemAdapter): Adapter that contains the configuration of the production system to use for optimization.
        optimization_time_portion (float): Portion of the total time that is used for optimization. Can reduce computation time significantly.
    """

    adapter: adapters.ProductionSystemData
    optimization_time_portion: float = 1.0

    model: Any = None
    x: Any = None
    z: Any = None
    s: Any = None
    a: Any = None
    v: Any = None
    t: Any = None

    processing_times_per_product_and_step: dict = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

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
        for product_type in self.adapter.product_data:
            x[product_type.ID] = {}
            work_piece_count = int(
                round(
                    self.adapter.scenario_data.constraints.target_product_count[
                        product_type.ID
                    ]
                    * self.optimization_time_portion,
                    0,
                )
            )
            for work_piece_index in range(work_piece_count):
                x[product_type.ID][work_piece_index] = {}
                for step in product_type.processes:
                    x[product_type.ID][work_piece_index][step] = {}
                    for station in range(
                        self.adapter.scenario_data.constraints.max_num_machines
                    ):
                        x[product_type.ID][work_piece_index][step][station] = (
                            self.model.addVar(
                                vtype=GRB.BINARY,
                                name="x[{},{},{},{}]".format(
                                    product_type.ID, work_piece_index, step, station
                                ),
                            )
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
        num_previous_machines = len(adapters.get_production_resources(self.adapter))
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
        self.check_all_process_steps_available_for_workpieces()
        self.check_module_available_at_station()
        self.check_breakdown_time_per_station()
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

    def check_all_process_steps_available_for_workpieces(self):
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

    def check_module_available_at_station(self):
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
        possible_states = [
            state for state in self.adapter.state_data if state.ID == state_id
        ]
        if not possible_states:
            return None
        return possible_states.pop()

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
            .location
        )

    def get_breakdown_values(self):
        machine_breakdown_state = self.get_state_with_id(
            optimization_util.BreakdownStateNamingConvention.MACHINE_BREAKDOWN_STATE.value
        )
        process_module_breakdown_state = self.get_state_with_id(
            optimization_util.BreakdownStateNamingConvention.PROCESS_MODULE_BREAKDOWN_STATE.value
        )
        process_modules, stations = self.get_process_modules_and_stations()
        BZ = self.adapter.scenario_data.info.time_range * self.optimization_time_portion

        if not machine_breakdown_state:
            machine_breakdown_count = 0
            machine_breakdown_time = 1
        else:
            MTTF_machine = self.get_expected_time_of_time_model_with_id(
                machine_breakdown_state.time_model_id
            )
            MTTR_machine = self.get_expected_time_of_time_model_with_id(
                machine_breakdown_state.repair_time_model_id
            )
            machine_breakdown_count = BZ / MTTF_machine
            machine_breakdown_time = MTTR_machine

        if not process_module_breakdown_state:
            module_breakdown_count = {module: 0 for module in process_modules}

            module_breakdown_time = {module: 1 for module in process_modules}
        else:
            MTTF_process_module = self.get_expected_time_of_time_model_with_id(
                process_module_breakdown_state.time_model_id
            )
            MTTR_process_module = self.get_expected_time_of_time_model_with_id(
                process_module_breakdown_state.repair_time_model_id
            )
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

    def check_breakdown_time_per_station(self):
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
        for product in self.adapter.product_data:
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
                processing_times_per_product_and_step[product.ID][step] = (
                    time_model.location + (time_model.scale * quantil)
                )
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
                * self.optimization_time_portion
                <= 0
            ),
            "Maximale_Ausfallzeit_einhalten",
        )

    def optimize(self, n_solutions=1):
        """
        Optimize the configuration of the production system.

        Args:
            n_solutions (int, optional): Number of solutions to find. Defaults to 1.
        """
        st = datetime.datetime.now()
        self.model: Any = gp.Model("MILP_Rekonfiguration")

        self.set_variables()
        self.set_constraints()
        self.set_objective_function()
        # Anzahl gewünschter Lösungen festlegen
        self.model.setParam(GRB.Param.PoolSolutions, n_solutions)
        # Finde die n besten Lösungen
        self.model.setParam(GRB.Param.PoolSearchMode, 2)

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

    def save_model(self, save_folder: str):
        """
        Saves the optimization model to a file with the name 'MILP.lp'.

        Args:
            save_folder (str): Folder to save the model in.
        """
        self.model.write(f"{save_folder}/MILP.lp")

    def save_results(
        self,
        optimizer: "Optimizer",
        adjusted_number_of_transport_resources: int = 1,
        number_of_seeds: int = 1,
    ):
        """
        Saves the results of the optimization, i.e. system configuration (`prodsys.adapters.ProductionSystemData`) and performance of the found configuration in a simulation run.

        For saving the configuration, some defaults attributes are used for non-found degrees of freedom in the optimization:

        - random location of a production resource
        - FIFO control policy for a production resource
        - FIFO control policy for a transport resource

        Args:
            save_folder (str): Folder to save the results in.
            adjusted_number_of_transport_resources (int, optional): Number of transport resources that are used for the optimization. Defaults to 1.
        """
        nSolutions = self.model.SolCount
        solution_dict = {"current_generation": "0", "hashes": {}}
        performances = {}
        performances["0"] = {}

        for result_counter in range(nSolutions):
            new_adapter = self.adapter.model_copy(deep=True)
            new_adapter.ID = str(uuid1())
            new_adapter.resource_data = [
                resource
                for resource in self.adapter.resource_data
                if not isinstance(resource, resource_data.ResourceData)
            ]
            adjust_number_of_transport_resources(
                new_adapter, adjusted_number_of_transport_resources
            )
            possible_positions = deepcopy(self.adapter.scenario_data.options.positions)

            self.model.setParam(GRB.Param.SolutionNumber, result_counter)
            # Retrieve from result the resource data that specifies the used process modules
            resources_data = []
            stations = self.get_process_modules_and_stations()[1]
            for station in stations:
                if self.s[station].Xn == 1:
                    resources_data.append(station)

            for resource_counter, resource in enumerate(resources_data):
                processes = []  # Ids for used process modules on this machine
                modules = self.get_process_modules_and_stations()[0]
                for module in modules:
                    if self.z[module, resource].Xn == 1:
                        processes.append(module)
                if not processes:
                    continue
                location = random.choice(possible_positions)
                possible_positions.remove(location)
                new_resource = resource_data.ResourceData(
                    ID="M" + str(resource_counter),
                    description="",
                    capacity=1,
                    location=location,
                    controller="PipelineController",
                    control_policy="FIFO",
                    process_ids=processes,
                    process_capacity=None,
                    # state_ids=states,
                )
                new_adapter.resource_data.append(new_resource)
                optimization_util.add_setup_states_to_machine(
                    new_adapter, new_resource.ID
                )
            adapter_manipulation.add_default_queues_to_resources(new_adapter)
            optimization_util.clean_out_breakdown_states_of_resources(new_adapter)
            optimization_util.adjust_process_capacities(new_adapter)

            fintess_values, event_log_dict = optimization.evaluate(
                self.adapter,
                solution_dict,
                number_of_seeds,
                new_adapter,
                optimizer.full_save,
            )
            optimizer.save_optimization_step(
                fintess_values, new_adapter, event_log_dict
            )


class MathOptHyperparameters(BaseModel):
    """
    Hyperparameters for configuration optimization with mathematical optimization. For mathetical optimization, only production capacity is optimized..
    Mathematical optimization is performed with Gurobi, so a valid Gurobi license is required.

    Args:
        optimization_time_portion (float): Portion of the total time that is used for optimization.
        number_of_solutions (int): Number of solutions that are generated.
        adjusted_number_of_transport_resources (int): Number of transport resources that are used for the optimization.
        number_of_seeds (int): Number of seeds for the simulation runs.
    """

    optimization_time_portion: float = 0.5
    number_of_solutions: int = 1
    adjusted_number_of_transport_resources: int = 1
    number_of_seeds: int = 1

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "optimization_time_portion": 0.5,
                    "number_of_solutions": 1,
                    "adjusted_number_of_transport_resources": 1,
                    "number_of_seeds": 1,
                },
            ]
        }
    )


def mathematical_optimization(
    optimizer: "Optimizer",
    # base_configuration: adapters.ProductionSystemAdapter,
    # hyper_parameters: MathOptHyperparameters,
    # save_folder: str = "results",
    # full_save: bool = False,
):
    """
    Optimize the configuration of the production system with mathematical optimization.

    Args:
        optimizer (Optimizer): The optimizer object containing the adapter, hyperparameters, and settings for optimization.
        base_configuration (adapters.ProductionSystemAdapter): Base configuration for the optimization.
        hyper_parameters (MathOptHyperparameters): Hyperparameters for configuration optimization with mathematical optimization.
        save_folder (str, optional): Folder to save the results in. Defaults to "results".
        full_save (bool, optional): Indicates if the full results are saved. Defaults to False.
    """
    adapters.ProductionSystemData.model_config["validate_assignment"] = False

    base_configuration = optimizer.adapter.model_copy(deep=True)
    if not adapters.check_for_clean_compound_processes(base_configuration):
        raise ValueError(
            "Compound processes are not supported in the current configuration."
        )
    if not check_breakdown_states_available(base_configuration):
        create_default_breakdown_states(base_configuration)

    model = MathOptimizer(
        adapter=optimizer.adapter,
        optimization_time_portion=optimizer.hyperparameters.optimization_time_portion,
    )

    model.optimize(n_solutions=optimizer.hyperparameters.number_of_solutions)
    model.save_model(save_folder=optimizer.save_folder)
    model.save_results(
        optimizer=optimizer,
        adjusted_number_of_transport_resources=optimizer.hyperparameters.adjusted_number_of_transport_resources,
        number_of_seeds=optimizer.hyperparameters.number_of_seeds,
    )
