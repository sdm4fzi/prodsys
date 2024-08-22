"""
This module contains the data structures for the scenario data that is used in optimization to determine the best configuration of a production system. A Scenario constists thereby of:
- `ScenarioConstrainsData`: The constraints of the scenario.
- `ScenarioOptionsData`: The options of the scenario.
- `ScenarioInfoData`: The information of the scenario.
- 'Objectives': The objectives of the scenario.
- `ScenarioData`: The scenario data that contains the constraints, options, information and objectives of the scenario. 
"""
from typing import List, Optional, Dict
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator, conlist

from prodsys.models.performance_indicators import KPIEnum
from prodsys.models.resource_data import ResourceControlPolicy, TransportControlPolicy
from prodsys.models.source_data import RoutingHeuristic


class ReconfigurationEnum(str, Enum):
    """
    Enum that represents the different levels of reconfigurations that are possible.

    - ProductionCapacity: Reconfiguration of production capacity (number of machines and their configuration)
    - TransportCapacity: Reconfiguration of transport capacity (number of transport resources and their configuration)
    - Layout: Reconfiguration of layout (only position of resources)
    - SequencingLogic: Reconfiguration of sequencing logic (only the control policy of resources)
    - RoutingLogic: Reconfiguration of routing logic (only the routing heuristic of routers)
    """

    PRODUCTION_CAPACITY = "production_capacity"
    TRANSPORT_CAPACITY = "transport_capacity"
    LAYOUT = "layout"
    SEQUENCING_LOGIC = "sequencing_logic"
    ROUTING_LOGIC = "routing_logic"


class ScenarioConstrainsData(BaseModel):
    """
    Class that represents the constraints of a scenario. The maximum limitations aim to limit the complexity of the
    scenario, thus optimization is possible in a reasonable time. However, by setting only a few constraints, the
    complexity of the scenario can be increased. E.g. you set the maximum reconfiguration cost to the targeted value and
    maximum numbers very high. Thereby, the optimization problem is only constrained by reconfiguration cost and not other
    factors.

    Args:
        max_reconfiguration_cost (float): Maximum reconfiguration cost that can be spend for new production capacity in the scenario.
        max_num_machines (int): Maximum number of machines that can be used in the scenario.
        max_num_processes_per_machine (int): Maximum number of processes that can be assigned to a machine in the scenario.
        max_num_transport_resources (int): Maximum number of transport resources that can be used in the scenario.
        target_product_count (Optional[Dict[str, int]], optional): Target product count for the scenario. Defaults to None. Mapping of product type to target count in the considered time range of the scenario.
    """

    max_reconfiguration_cost: float
    max_num_machines: int
    max_num_processes_per_machine: int
    max_num_transport_resources: int
    target_product_count: Optional[Dict[str, int]]

    model_config=ConfigDict(json_schema_extra={
        "examples": [
            {
                "max_reconfiguration_cost": 120000,
                "max_num_machines": 10,
                "max_num_processes_per_machine": 2,
                "max_num_transport_resources": 2,
                "target_product_count": {"Product_1": 120, "Product_2": 200},
            }
        ]
    })

class ScenarioOptionsData(BaseModel):
    """
    Class that represents the options of a scenario. The options are used to define the deegrees of freedom in the
    optimization scenario, i.e. the different possibilities to adjust the configuration to find a solution with higher
    performance. Options consider possible transformations of the configuration, possible logics of controllers and routers
    and possible positions of machines in the layout.

    Args:
        transformations (List[ReconfigurationEnum]): List of possible transformations of the configuration.
        machine_controllers (List[Literal["FIFO", "LIFO", "SPT"]]): List of possible controllers for machines.
        transport_controllers (List[Literal["FIFO", "SPT_transport", "Nearest_origin_and_longest_target_queues_transport", "Nearest_origin_and_shortest_target_input_queues_transport"]]): List of possible controllers for transport resources.
        routing_heuristics (List[Literal["shortest_queue", "random", "FIFO"]]): List of possible routing heuristics for sources.
        positions (List[conlist(float, min_length=2, max_length=2)]): List of possible positions for machines in the layout.

    Raises:
        ValueError: If the positions are not a list of tuples of length 2.
    """

    transformations: List[ReconfigurationEnum]
    machine_controllers: List[ResourceControlPolicy]
    transport_controllers: List[TransportControlPolicy]
    routing_heuristics: List[RoutingHeuristic]
    positions: List[conlist(float, min_length=2, max_length=2)] # type: ignore

    @field_validator("positions")
    def check_positions(cls, v):
        for e in v:
            if len(e) != 2:
                raise ValueError("positions must be a list of tuples of length 2")
        return v

    model_config=ConfigDict(json_schema_extra={
        "examples": [
            {
                "transformations": [
                    "production_capacity",
                    "transport_capacity",
                    "layout",
                    "sequencing_logic",
                    "routing_logic",
                ],
                "machine_controllers": ["FIFO", "LIFO", "SPT"],
                "transport_controllers": ["FIFO", "SPT_transport"],
                "routing_heuristics": ["shortest_queue", "random", "FIFO"],
                "positions": [[10.0, 10.0], [20.0, 20.0]],
            }
        ]
    })


class ScenarioInfoData(BaseModel):
    """
    Class that represents the information of a scenario. The information is used to define some parameters that allow
    evaluation of the scenario.

    Args:
        machine_cost (float): Cost of a machine.
        transport_resource_cost (float): Cost of a transport resource.
        process_module_cost (float): Cost of a process module.
        breakdown_cost (Optional[float], optional): Cost of a breakdown. Defaults to None.
        time_range (Optional[int], optional): Time range of the scenario in minutes to be considered. Defaults to None.
        maximum_breakdown_time (Optional[int], optional): Maximum allowable breakdown time in the scenario in minutes. Defaults to None.
    """

    machine_cost: float
    transport_resource_cost: float
    process_module_cost: float
    breakdown_cost: Optional[float]
    time_range: Optional[int]
    maximum_breakdown_time: Optional[int]

    model_config=ConfigDict(json_schema_extra={
        "examples": [
            {
                "machine_cost": 30000,
                "transport_resource_cost": 20000,
                "process_module_cost": 2300,
                "breakdown_cost": 1000,
                "time_range": 2600,
                "maximum_breakdown_time": 10,
            }
        ]
    })


class Objective(BaseModel):
    name: KPIEnum
    weight: float = 1.0

    model_config=ConfigDict(json_schema_extra={
        "examples": [
            {
                "name": KPIEnum.COST,
                "weight": 0.6,
            },
            {
                "name": KPIEnum.THROUGHPUT,
                "weight": 0.1,
            },
            {
                "name": KPIEnum.WIP,
                "weight": 0.5,
            },
        ]
    })


class ScenarioData(BaseModel):
    """
    Class that represents a scenario and contraints data about constaints, options, information and objectives of the scenario.

    Args:
        constraints (ScenarioConstrainsData): Constraints of the scenario.
        options (ScenarioOptionsData): Options of the scenario.
        info (ScenarioInfoData): Information of the scenario.
        optimize (List[Objectives]): List of KPIs that should be optimized.

    Raises:
        ValueError: If the weights are not specified for all KPIs that should be optimized.
    """

    constraints: ScenarioConstrainsData
    options: ScenarioOptionsData
    info: ScenarioInfoData
    objectives: List[Objective]

    model_config=ConfigDict(use_enum_values=True, json_schema_extra={
        "examples": [
            {
                "summary": "Scenario",
                "value": {
                    "constraints": {
                        "max_reconfiguration_cost": 120000,
                        "max_num_machines": 10,
                        "max_num_processes_per_machine": 2,
                        "max_num_transport_resources": 2,
                        "target_product_count": {"Product_1": 120, "Product_2": 200},
                    },
                    "options": {
                        "transformations": [
                            "production_capacity",
                            "transport_capacity",
                            "layout",
                            "sequencing_logic",
                            "routing_logic",
                        ],
                        "machine_controllers": ["FIFO", "LIFO", "SPT"],
                        "transport_controllers": ["FIFO", "SPT_transport"],
                        "routing_heuristics": ["shortest_queue", "random", "FIFO"],
                        "positions": [[10.0, 10.0], [20.0, 20.0]],
                    },
                    "info": {
                        "machine_cost": 30000,
                        "transport_resource_cost": 20000,
                        "process_module_cost": 2300,
                        "breakdown_cost": 1000,
                        "time_range": 2600,
                        "maximum_breakdown_time": 10,
                    },
                    "objectives": [
                        {
                            "name": KPIEnum.COST,
                            "weight": 0.6,
                        },
                        {
                            "name": KPIEnum.THROUGHPUT,
                            "weight": 0.1,
                        },
                        {
                            "name": KPIEnum.WIP,
                            "weight": 0.5,
                        },
                    ],
                },
            }
        ]
    })
