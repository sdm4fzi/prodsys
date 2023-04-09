from typing import List, Dict, Literal, Union

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json


from pydantic import BaseModel
from prodsim.data_structures import (
    time_model_data,
    resource_data,
    queue_data,
    state_data,
    material_data,
    processes_data,
    source_data,
    sink_data,
    performance_data,
    performance_indicators,
    scenario_data,
)
from prodsim.util import evolutionary_algorithm, tabu_search, simulated_annealing, math_opt, util
import prodsim

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:4200",
    "http://127.0.0.1",
    "http://127.0.0.1:4200",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

description = """
The ProdSim-API allows you to create and run production simulations and optimizations with the ProdSim library. 
"""

app = FastAPI(
    title="ProdSim API",
    description=description,
    version="0.0.1",
    contact={
        "name": "Sebastian Behrendt",
        "email": "sebastianbehrendt97@gmail.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://mit-license.org/",
    },
)


class Project(BaseModel):
    ID: str
    adapters: Dict[str, prodsim.adapters.JsonAdapter] = {}

    class Config:
        schema_extra = {
            "example": {
                "ID": "Example Project",
                "adapters": {
                    "adapter1": {
                        "seed": 24,
                        "time_models": {
                            "0": {
                                "ID": "function_time_model_1",
                                "description": "normal distribution time model with 20 minutes",
                                "type": "FunctionTimeModel",
                                "distribution_function": "normal",
                                "parameters": [14.3, 5.0],
                                "batch_size": 100,
                            },
                            "1": {
                                "ID": "function_time_model_2",
                                "description": "constant distribution time model with 10 minutes",
                                "type": "FunctionTimeModel",
                                "distribution_function": "constant",
                                "parameters": [15.0],
                                "batch_size": 100,
                            },
                            "2": {
                                "ID": "function_time_model_3",
                                "description": "normal distribution time model with 20 minutes",
                                "type": "FunctionTimeModel",
                                "distribution_function": "normal",
                                "parameters": [20.0, 5.0],
                                "batch_size": 100,
                            },
                            "3": {
                                "ID": "function_time_model_4",
                                "description": "exponential distribution time model with 100 minutes",
                                "type": "FunctionTimeModel",
                                "distribution_function": "exponential",
                                "parameters": [52.0],
                                "batch_size": 100,
                            },
                            "4": {
                                "ID": "function_time_model_5",
                                "description": "exponential distribution time model with 150 minutes",
                                "type": "FunctionTimeModel",
                                "distribution_function": "exponential",
                                "parameters": [150.0],
                                "batch_size": 100,
                            },
                            "5": {
                                "ID": "history_time_model_1",
                                "description": "history time model",
                                "type": "HistoryTimeModel",
                                "history": [25.0, 13.0, 15.0, 16.0, 17.0, 20.0, 21.0],
                            },
                            "6": {
                                "ID": "manhattan_time_model_1",
                                "description": "manhattan time model with speed 180 m/min = 3 m/s",
                                "type": "ManhattanDistanceTimeModel",
                                "speed": 30.0,
                                "reaction_time": 0.15,
                            },
                        },
                        "states": {
                            "0": {
                                "ID": "Breakdownstate_1",
                                "description": "Breakdown state machine 1",
                                "time_model_id": "function_time_model_5",
                                "type": "BreakDownState",
                            },
                            "1": {
                                "ID": "Breakdownstate_2",
                                "description": "Breakdown state machine 2",
                                "time_model_id": "function_time_model_5",
                                "type": "BreakDownState",
                            },
                            "2": {
                                "ID": "Setup_State_1",
                                "description": "Setup state machine 1",
                                "time_model_id": "function_time_model_2",
                                "type": "SetupState",
                                "origin_setup": "P1",
                                "target_setup": "P2",
                            },
                            "3": {
                                "ID": "Setup_State_2",
                                "description": "Setup state machine 2",
                                "time_model_id": "function_time_model_2",
                                "type": "SetupState",
                                "origin_setup": "P2",
                                "target_setup": "P1",
                            },
                            "4": {
                                "ID": "Setup_State_3",
                                "description": "Setup state machine 3",
                                "time_model_id": "function_time_model_2",
                                "type": "SetupState",
                                "origin_setup": "P1",
                                "target_setup": "P3",
                            },
                            "5": {
                                "ID": "Setup_State_4",
                                "description": "Setup state machine 3",
                                "time_model_id": "function_time_model_3",
                                "type": "SetupState",
                                "origin_setup": "P3",
                                "target_setup": "P1",
                            },
                            "6": {
                                "ID": "ProcessBreakdownState_1",
                                "description": "Breakdown state process 1",
                                "time_model_id": "function_time_model_5",
                                "type": "ProcessBreakDownState",
                                "process_id": "P1",
                            },
                        },
                        "processes": {
                            "0": {
                                "ID": "P1",
                                "description": "Process 1",
                                "time_model_id": "function_time_model_1",
                                "type": "ProductionProcesses",
                            },
                            "1": {
                                "ID": "P2",
                                "description": "Process 2",
                                "time_model_id": "function_time_model_2",
                                "type": "ProductionProcesses",
                            },
                            "2": {
                                "ID": "P3",
                                "description": "Process 3",
                                "time_model_id": "function_time_model_3",
                                "type": "ProductionProcesses",
                            },
                            "3": {
                                "ID": "TP1",
                                "description": "Transport Process 1",
                                "time_model_id": "manhattan_time_model_1",
                                "type": "TransportProcesses",
                            },
                        },
                        "queues": {
                            "0": {
                                "ID": "IQ1",
                                "description": "Input-queue 1 for R1 and R2",
                                "capacity": 10,
                            },
                            "1": {
                                "ID": "OQ1",
                                "description": "Output-queue 1 for R1",
                                "capacity": 10,
                            },
                            "2": {
                                "ID": "OQ2",
                                "description": "Output-queue 2 for R2",
                                "capacity": 10,
                            },
                            "3": {
                                "ID": "IQ2",
                                "description": "Input-queue 2 for R3",
                                "capacity": 10,
                            },
                            "4": {
                                "ID": "OQ3",
                                "description": "Output-queue 3 for R3",
                                "capacity": 10,
                            },
                            "5": {
                                "ID": "SourceQueue",
                                "description": "Output-Queue for all sources",
                                "capacity": 0,
                            },
                            "6": {
                                "ID": "SinkQueue",
                                "description": "Input-Queue for all sinks",
                                "capacity": 0,
                            },
                        },
                        "resources": {
                            "0": {
                                "ID": "R1",
                                "description": "Resource 1",
                                "capacity": 2,
                                "location": [10.0, 10.0],
                                "controller": "SimpleController",
                                "control_policy": "FIFO",
                                "processes": ["P1", "P2"],
                                "process_capacity": [2, 1],
                                "states": [
                                    "Breakdownstate_1",
                                    "Setup_State_1",
                                    "Setup_State_2",
                                    "ProcessBreakdownState_1",
                                ],
                                "input_queues": ["IQ1"],
                                "output_queues": ["OQ1"],
                            },
                            "1": {
                                "ID": "R2",
                                "description": "Resource 2",
                                "capacity": 1,
                                "location": [20.0, 10.0],
                                "controller": "SimpleController",
                                "control_policy": "FIFO",
                                "processes": ["P2", "P3"],
                                "process_capacity": None,
                                "states": ["Breakdownstate_2"],
                                "input_queues": ["IQ1"],
                                "output_queues": ["OQ2"],
                            },
                            "2": {
                                "ID": "R3",
                                "description": "Resource 3",
                                "capacity": 2,
                                "location": [20.0, 20.0],
                                "controller": "SimpleController",
                                "control_policy": "FIFO",
                                "processes": ["P1", "P3"],
                                "process_capacity": [1, 2],
                                "states": [
                                    "Breakdownstate_1",
                                    "Breakdownstate_2",
                                    "Setup_State_3",
                                    "Setup_State_4",
                                ],
                                "input_queues": ["IQ2"],
                                "output_queues": ["OQ3"],
                            },
                            "3": {
                                "ID": "R4",
                                "description": "Resource 3",
                                "capacity": 2,
                                "location": [10.0, 20.0],
                                "controller": "SimpleController",
                                "control_policy": "FIFO",
                                "processes": ["P1", "P3"],
                                "process_capacity": [2, 2],
                                "states": [
                                    "Breakdownstate_1",
                                    "Setup_State_3",
                                    "Setup_State_4",
                                ],
                                "input_queues": ["IQ2"],
                                "output_queues": ["OQ3"],
                            },
                            "4": {
                                "ID": "TR1",
                                "description": "Transport Resource 1",
                                "capacity": 1,
                                "location": [15.0, 15.0],
                                "controller": "TransportController",
                                "control_policy": "FIFO",
                                "processes": ["TP1"],
                                "process_capacity": None,
                                "states": ["Breakdownstate_1"],
                            },
                            "5": {
                                "ID": "TR2",
                                "description": "Transport Resource 2",
                                "capacity": 1,
                                "location": [15.0, 20.0],
                                "controller": "TransportController",
                                "control_policy": "SPT_transport",
                                "processes": ["TP1"],
                                "process_capacity": None,
                                "states": ["Breakdownstate_1"],
                            },
                        },
                        "materials": {
                            "0": {
                                "ID": "Material_1",
                                "description": "Material 1",
                                "material_type": "Material_1",
                                "processes": ["P1", "P2", "P3"],
                                "transport_process": "TP1",
                            },
                            "1": {
                                "ID": "Material_2",
                                "description": "Material 2",
                                "material_type": "Material_2",
                                "processes": ["P1", "P2", "P3", "P1"],
                                "transport_process": "TP1",
                            },
                            "2": {
                                "ID": "Material_3",
                                "description": "Material 3",
                                "material_type": "Material_3",
                                "processes": "data/example_material_petri_net.pnml",
                                "transport_process": "TP1",
                            },
                        },
                        "sinks": {
                            "0": {
                                "ID": "SK1",
                                "description": "Sink 1",
                                "location": [50.0, 50.0],
                                "material_type": "Material_1",
                                "input_queues": ["SinkQueue"],
                            },
                            "1": {
                                "ID": "SK2",
                                "description": "Sink 2",
                                "location": [55.0, 50.0],
                                "material_type": "Material_2",
                                "input_queues": ["SinkQueue"],
                            },
                            "2": {
                                "ID": "SK3",
                                "description": "Sink 3",
                                "location": [45.0, 50.0],
                                "material_type": "Material_3",
                                "input_queues": ["SinkQueue"],
                            },
                        },
                        "sources": {
                            "0": {
                                "ID": "S1",
                                "description": "Source 1",
                                "location": [0.0, 0.0],
                                "material_type": "Material_1",
                                "time_model_id": "function_time_model_4",
                                "router": "SimpleRouter",
                                "routing_heuristic": "shortest_queue",
                                "output_queues": ["SourceQueue"],
                            },
                            "1": {
                                "ID": "S2",
                                "description": "Source 2",
                                "location": [30.0, 30.0],
                                "material_type": "Material_2",
                                "time_model_id": "function_time_model_4",
                                "router": "SimpleRouter",
                                "routing_heuristic": "shortest_queue",
                                "output_queues": ["SourceQueue"],
                            },
                            "2": {
                                "ID": "S3",
                                "description": "Source 3",
                                "location": [40.0, 30.0],
                                "material_type": "Material_3",
                                "time_model_id": "function_time_model_4",
                                "router": "SimpleRouter",
                                "routing_heuristic": "shortest_queue",
                                "output_queues": ["SourceQueue"],
                            },
                        },
                    }
                },
            }
        }


database: List[Project] = []
results_database: Dict[str, performance_data.Performance] = {}


@app.get("/", response_model=str)
async def root():
    return "prodsim API v1.0"


def get_projects() -> List[Project]:
    return database


def get_project(project_id: str) -> Project:
    for project in database:
        if project.ID == project_id:
            return project
    raise HTTPException(404, f"Project {project_id} not found")

def evaluate(adapter_object: prodsim.adapters.JsonAdapter) -> str:
    runner_object = prodsim.runner.Runner(adapter=adapter_object)
    runner_object.initialize_simulation()
    runner_object.run(5000)
    performance = runner_object.get_performance_data()
    results_database[adapter_object.ID] = performance

@app.get("/load_example_project", response_model=str, tags=["projects"])
async def load_example_project() -> str:
    example_project = Project(ID="example_project")
    database.append(example_project)
    
    adapter_object = prodsim.adapters.JsonAdapter(ID="example_adapter_1")
    adapter_object.read_data('examples/basic_example/example_configuration.json')
    evaluate(adapter_object)
    example_project.adapters[adapter_object.ID] = adapter_object

    return "Sucessfully loaded example project"

@app.get("/load_optimization_example", response_model=str, tags=["projects"])
async def load_example_project() -> str:
    example_project = Project(ID="example_optimization_project")
    database.append(example_project)
    
    adapter_object = prodsim.adapters.JsonAdapter(ID="example_adapter_1")
    adapter_object.read_data('examples/optimization_example/base_scenario.json', 
                             "examples/optimization_example/scenario.json")
    example_project.adapters[adapter_object.ID] = adapter_object

    return "Sucessfully loaded optimization example project. Optimizations runs can be started now."


@app.get("/projects", response_model=List[Project], tags=["projects"])
async def read_projects() -> List[Project]:
    return get_projects()


@app.put("/projects", tags=["projects"])
async def create_project(project: Project) -> str:
    database.append(project)
    return "Sucessfully created project with ID: " + project.ID


@app.get("/projects/{project_id}", response_model=Project, tags=["projects"])
async def read_project(project_id: str) -> Project:
    return get_project(project_id)


@app.delete("/projects/{project_id}", tags=["projects"])
async def delete_project(project_id: str):
    project = get_project(project_id)
    database.remove(project)
    return "Sucessfully deleted project with ID: " + project_id


@app.put("/projects/{project_id}/adapters", tags=["adapters"])
async def create_adapter(project_id: str, adapter: prodsim.adapters.JsonAdapter):
    project = get_project(project_id)
    project.adapters.append(adapter)
    return "Sucessfully created adapter with ID: " + adapter.ID


@app.get(
    "/projects/{project_id}/adapters",
    response_model=Dict[str, prodsim.adapters.JsonAdapter],
    tags=["adapters"],
)
async def read_adapters(project_id: str):
    project = get_project(project_id)
    return project.adapters


def get_adapter(project_id: str, adapter_id: str) -> prodsim.adapters.JsonAdapter:
    project = get_project(project_id)
    if adapter_id not in project.adapters:
        raise HTTPException(
            404, f"Adapter {adapter_id} not found in project {project_id}"
        )
    return project.adapters[adapter_id]


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}",
    response_model=prodsim.adapters.JsonAdapter,
    tags=["adapters"],
)
async def read_adapter(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter


@app.put("/projects/{project_id}/adapters/{adapter_id}", tags=["adapters"])
async def update_adapter(
    project_id: str, adapter_id: str, ada: prodsim.adapters.JsonAdapter
):
    project = get_project(project_id)
    project.adapters[adapter_id] = ada
    return "Sucessfully updated adapter with ID: " + adapter_id


@app.delete("/projects/{project_id}/adapters/{adapter_id}", tags=["adapters"])
async def delete_adapter(project_id: str, adapter_id: str):
    project = get_project(project_id)
    adapter = get_adapter(project_id, adapter_id)
    project.adapters.pop(adapter_id)
    return "Sucessfully deleted adapter with ID: " + adapter_id


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/run_simulation", tags=["simulation"]
)
async def run_simulation(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    runner_object = prodsim.runner.Runner(adapter=adapter)
    runner_object.initialize_simulation()
    runner_object.run(3000)
    performance = runner_object.get_performance_data()
    results_database[adapter_id] = performance
    return "Sucessfully ran simulation for adapter with ID: " + adapter_id



@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/optimize_configuration", tags=["optimization"]
)
async def run_configuration_optimization(project_id: str, adapter_id: str, hyper_parameters: Union[evolutionary_algorithm.EvolutionaryAlgorithmHyperparameters, str]):
    adapter = get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(
            404, f"Adapter {adapter_id} is missing scenario data for optimization."
        )
    configuration_file_path = f"data/{project_id}/{adapter_id}_configuration.json"
    scenario_file_path = f"data/{project_id}/{adapter_id}_scenario.json"
    save_folder = f"data/{project_id}/{adapter_id}"
    util.prepare_save_folder(save_folder)
    adapter.write_data(configuration_file_path)
    adapter.write_scenario_data(scenario_file_path)
    
    if isinstance(hyper_parameters, evolutionary_algorithm.EvolutionaryAlgorithmHyperparameters):
        optimization_func = evolutionary_algorithm.optimize_configuration
        # TODO: add here also the other optimizers!
    else:
        raise HTTPException(
            404, f"Wrong Hyperparameters for optimization."
        )
    
    optimization_func(save_folder=save_folder,
                      base_configuration_file_path=configuration_file_path,
                      scenario_file_path=scenario_file_path,
                      hyper_parameters=hyper_parameters
                      )
    return f"Succesfully optimized configuration of {adapter_id} in {project_id}."

# TODO: create response model for results for openAPI documentation. 
@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/optimize_configuration/results", tags=["optimization"]
)
def get_optimization_core_results(project_id: str, adapter_id: str):
    with open(f"data/{project_id}/{adapter_id}/optimization_results.json") as json_file:
        data = json.load(json_file)
    return data


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/optimize_configuration/{solution_id}", tags=["optimization"], response_model=prodsim.adapters.JsonAdapter
)
def get_optimization_solution(project_id: str, adapter_id: str, solution_id: str) -> prodsim.adapters.JsonAdapter:
    with open(f"data/{project_id}/{adapter_id}/{solution_id}.json") as json_file:
        data = json.load(json_file)
    return data


def get_result(project_id: str, adapter_id: str) -> performance_data.Performance:
    if adapter_id not in results_database:
        raise HTTPException(
            404, f"Results for adapter {adapter_id} not found in project {project_id}"
        )
    return results_database[adapter_id]


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/results/static_results",
    response_model=List[performance_indicators.KPI_UNION],
    tags=["results"],
)
async def get_all_results(project_id: str, adapter_id: str):
    result = get_result(project_id, adapter_id)
    return result.kpis

@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/results/event_results",
    response_model=List[performance_data.Event],
    tags=["results"],
)
async def get_event_results(project_id: str, adapter_id: str):
    result = get_result(project_id, adapter_id)
    return result.event_log


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/results/{kpi}",
    response_model=List[performance_indicators.KPI_UNION],
    tags=["results"],
)
async def get_output_results(
    project_id: str, adapter_id: str, kpi: performance_indicators.KPIEnum
):
    enum_values = tuple(item.value for item in performance_indicators.KPIEnum)
    if kpi not in enum_values:
        raise HTTPException(404, f"KPI {kpi} not found")
    result = get_result(project_id, adapter_id)

    output = [
        kpi_to_select for kpi_to_select in result.kpis if kpi_to_select.name == kpi
    ]
    return output


#################### Time model data ####################


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/time_models",
    response_model=List[time_model_data.TIME_MODEL_DATA],
    tags=["time_models"],
)
async def read_time_models(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.time_model_data


def get_time_model(project_id: str, adapter_id: str, time_model_id: str):
    adapter = get_adapter(project_id, adapter_id)
    for time_model in adapter.time_model_data:
        if time_model.ID == time_model_id:
            return time_model
    raise HTTPException(404, "Time model not found")


@app.put(
    "/projects/{project_id}/adapters/{adapter_id}/time_models/{time_model_id}",
    tags=["time_models"],
)
async def create_time_model(
    project_id: str,
    adapter_id: str,
    time_model_id,
    time_model: time_model_data.TIME_MODEL_DATA,
):
    if time_model.ID != time_model_id:
        raise HTTPException(404, "Time model ID must not be changed")
    adapter = get_adapter(project_id, adapter_id)
    adapter.time_model_data.append(time_model)
    return "Sucessfully created time model with ID: " + time_model.ID


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/time_models/{time_model_id}",
    response_model=time_model_data.TIME_MODEL_DATA,
    tags=["time_models"],
)
async def read_time_model(project_id: str, adapter_id: str, time_model_id: str):
    time_model = get_time_model(project_id, adapter_id, time_model_id)
    return time_model


#################### Material Data ####################


def get_material(project_id: str, adapter_id: str, material_id: str):
    adapter = get_adapter(project_id, adapter_id)
    for material in adapter.material_data:
        if material.ID == material_id:
            return material
    raise HTTPException(404, "Material not found")


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/materials",
    response_model=List[material_data.MaterialData],
    tags=["materials"],
)
async def read_materials(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.material_data


@app.put(
    "/projects/{project_id}/adapters/{adapter_id}/materials/{material_id}",
    tags=["materials"],
)
async def create_material(
    project_id: str,
    adapter_id: str,
    material_id,
    material: material_data.MaterialData,
):
    if material.ID != material_id:
        raise HTTPException(404, "Material ID must not be changed")
    adapter = get_adapter(project_id, adapter_id)
    adapter.material_data.append(material)
    return "Sucessfully created material with ID: " + material.ID


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/materials/{material_id}",
    response_model=material_data.MaterialData,
    tags=["materials"],
)
async def read_material(project_id: str, adapter_id: str, material_id: str):
    material = get_material(project_id, adapter_id, material_id)
    return material


#################### Process Data ####################


def get_process(project_id: str, adapter_id: str, process_id: str):
    adapter = get_adapter(project_id, adapter_id)
    for process in adapter.process_data:
        if process.ID == process_id:
            return process
    raise HTTPException(404, "Process not found")


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/processes",
    response_model=List[processes_data.ProcessData],
    tags=["processes"],
)
async def read_processes(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.process_data


@app.put(
    "/projects/{project_id}/adapters/{adapter_id}/processes/{process_id}",
    tags=["processes"],
)
async def create_process(
    project_id: str,
    adapter_id: str,
    process_id,
    process: processes_data.ProcessData,
):
    if process.ID != process_id:
        raise HTTPException(404, "Process ID must not be changed")
    adapter = get_adapter(project_id, adapter_id)
    adapter.process_data.append(process)
    return "Sucessfully created process with ID: " + process.ID


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/processes/{process_id}",
    response_model=processes_data.ProcessData,
    tags=["processes"],
)
async def read_process(project_id: str, adapter_id: str, process_id: str):
    process = get_process(project_id, adapter_id, process_id)
    return process


#################### Queue Data ####################


def get_queue_data(project_id: str, adapter_id: str, queue_id: str):
    adapter = get_adapter(project_id, adapter_id)
    for queue_data in adapter.queue_data:
        if queue_data.ID == queue_id:
            return queue_data
    raise HTTPException(404, "Queue not found")


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/queues",
    response_model=List[queue_data.QueueData],
    tags=["queues"],
)
async def read_queues(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.queue_data


@app.put(
    "/projects/{project_id}/adapters/{adapter_id}/queues/{queue_id}", tags=["queues"]
)
async def create_queue(
    project_id: str,
    adapter_id: str,
    queue_id,
    queue: queue_data.QueueData,
):
    if queue.ID != queue_id:
        raise HTTPException(404, "Queue ID must not be changed")
    adapter = get_adapter(project_id, adapter_id)
    adapter.queue_data.append(queue)
    return "Sucessfully created queue with ID: " + queue.ID


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/queues/{queue_id}",
    response_model=queue_data.QueueData,
    tags=["queues"],
)
async def read_queue(project_id: str, adapter_id: str, queue_id: str):
    queue = get_queue_data(project_id, adapter_id, queue_id)
    return queue


####################### Resource Data ############################


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/resources",
    response_model=List[resource_data.RESOURCE_DATA_UNION],
    tags=["resources"],
)
async def read_resources(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.resource_data


def get_resource(project_id: str, adapter_id: str, resource_id: str):
    adapter = get_adapter(project_id, adapter_id)
    for resource in adapter.resource_data:
        if resource.ID == resource_id:
            return resource
    raise HTTPException(
        404,
        f"Resource {resource_id} not found in adapter {adapter_id} for project {project_id}",
    )


@app.delete(
    "/projects/{project_id}/adapters/{adapter_id}/resources/{resource_id}",
    tags=["resources"],
)
async def delete_resource(project_id: str, adapter_id: str, resource_id: str):
    adapter = get_adapter(project_id, adapter_id)
    resource = get_resource(project_id, adapter_id, resource_id)
    adapter.resource_data.remove(resource)
    return "Sucessfully deleted resource with ID: " + resource_id


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/resources/{resource_id}",
    response_model=resource_data.RESOURCE_DATA_UNION,
    tags=["resources"],
)
async def read_resource(project_id: str, adapter_id: str, resource_id: str):
    resource = get_resource(project_id, adapter_id, resource_id)
    return resource


@app.put(
    "/projects/{project_id}/adapters/{adapter_id}/resources/{resource_id}",
    tags=["resources"],
)
async def create_resource(
    project_id: str,
    adapter_id: str,
    resource_id: str,
    resource: resource_data.RESOURCE_DATA_UNION,
):
    if resource.ID != resource_id:
        raise HTTPException(404, "Resource ID must not be changed")
    adapter = get_adapter(project_id, adapter_id)
    adapter.resource_data.append(resource)
    return "Sucessfully updated resource with ID: " + resource_id


####################### Sink Data ############################


def get_sink(project_id: str, adapter_id: str, sink_id: str):
    adapter = get_adapter(project_id, adapter_id)
    for sink in adapter.sink_data:
        if sink.ID == sink_id:
            return sink
    raise HTTPException(404, "Sink not found")


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/sinks",
    response_model=List[sink_data.SinkData],
    tags=["sinks"],
)
async def read_sinks(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.sink_data


@app.put("/projects/{project_id}/adapters/{adapter_id}/sinks/{sink_id}", tags=["sinks"])
async def create_sink(
    project_id: str,
    adapter_id: str,
    sink_id,
    sink: sink_data.SinkData,
):
    if sink.ID != sink_id:
        raise HTTPException(404, "Sink ID must not be changed")
    adapter = get_adapter(project_id, adapter_id)
    adapter.sink_data.append(sink)
    return "Sucessfully created sink with ID: " + sink.ID


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/sinks/{sink_id}",
    response_model=sink_data.SinkData,
    tags=["sinks"],
)
async def read_sink(project_id: str, adapter_id: str, sink_id: str):
    sink = get_sink(project_id, adapter_id, sink_id)
    return sink


####################### Source Data ############################


def get_source(project_id: str, adapter_id: str, source_id: str):
    adapter = get_adapter(project_id, adapter_id)
    for source in adapter.source_data:
        if source.ID == source_id:
            return source
    raise HTTPException(404, "Source not found")


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/sources",
    response_model=List[source_data.SourceData],
    tags=["sources"],
)
async def read_sources(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.source_data


@app.put(
    "/projects/{project_id}/adapters/{adapter_id}/sources/{source_id}", tags=["sources"]
)
async def create_source(
    project_id: str,
    adapter_id: str,
    source_id,
    source: source_data.SourceData,
):
    if source.ID != source_id:
        raise HTTPException(404, "Source ID must not be changed")
    adapter = get_adapter(project_id, adapter_id)
    adapter.source_data.append(source)
    return "Sucessfully created source with ID: " + source.ID


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/sources/{source_id}",
    response_model=source_data.SourceData,
    tags=["sources"],
)
async def read_source(project_id: str, adapter_id: str, source_id: str):
    source = get_source(project_id, adapter_id, source_id)
    return source


####################### State Data ############################


def get_state(project_id: str, adapter_id: str, state_id: str):
    adapter = get_adapter(project_id, adapter_id)
    for state in adapter.state_data:
        if state.ID == state_id:
            return state
    raise HTTPException(404, "State not found")


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/states",
    response_model=List[state_data.StateData],
    tags=["states"],
)
async def read_states(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.state_data


@app.put(
    "/projects/{project_id}/adapters/{adapter_id}/states/{state_id}", tags=["states"]
)
async def create_state(
    project_id: str,
    adapter_id: str,
    state_id,
    state: state_data.StateData,
):
    if state.ID != state_id:
        raise HTTPException(404, "State ID must not be changed")
    adapter = get_adapter(project_id, adapter_id)
    adapter.state_data.append(state)
    return "Sucessfully created state with ID: " + state.ID


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/states/{state_id}",
    response_model=state_data.StateData,
    tags=["states"],
)
async def read_state(project_id: str, adapter_id: str, state_id: str):
    state = get_state(project_id, adapter_id, state_id)
    return state


####################### Scenario Data ############################


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/scenario",
    response_model=scenario_data.ScenarioData,
    tags=["scenario"],
)
async def read_scenario(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.scenario_data


@app.put("/projects/{project_id}/adapters/{adapter_id}/scenario", tags=["scenario"])
async def create_scenario(
    project_id: str,
    adapter_id: str,
    scenario: scenario_data.ScenarioData,
):
    adapter = get_adapter(project_id, adapter_id)
    adapter.scenario_data = scenario
    return "Sucessfully created scenario"

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)