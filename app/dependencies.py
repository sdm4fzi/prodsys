from typing import Dict, List

import os

from fastapi import HTTPException
import prodsys
from prodsys.models import performance_data

from .models.projects import Project

print("create database")
database: List[Project] = []
results_database: Dict[str, performance_data.Performance] = {}


def get_projects() -> List[Project]:
    return database

def get_project(project_id: str) -> Project:
    for project in database:
        if project.ID == project_id:
            return project
    raise HTTPException(404, f"Project {project_id} not found")

def get_adapter(project_id: str, adapter_id: str) -> prodsys.adapters.JsonProductionSystemAdapter:
    project = get_project(project_id)
    if adapter_id not in project.adapters:
        raise HTTPException(
            404, f"Adapter {adapter_id} not found in project {project_id}"
        )
    return project.adapters[adapter_id]


def evaluate(adapter_object: prodsys.adapters.JsonProductionSystemAdapter) -> str:
    runner_object = prodsys.runner.Runner(adapter=adapter_object)
    runner_object.initialize_simulation()
    if adapter_object.scenario_data and adapter_object.scenario_data.info.time_range:
        run_length = adapter_object.scenario_data.info.time_range
    else:
        run_length = 5 * 7 * 24 * 60
    runner_object.run(run_length)
    performance = runner_object.get_performance_data()
    results_database[adapter_object.ID] = performance

def get_result(project_id: str, adapter_id: str) -> performance_data.Performance:
    if adapter_id not in results_database:
        raise HTTPException(
            404, f"Results for adapter {adapter_id} not found in project {project_id}"
        )
    return results_database[adapter_id]

def get_time_model(project_id: str, adapter_id: str, time_model_id: str):
    adapter = get_adapter(project_id, adapter_id)
    for time_model in adapter.time_model_data:
        if time_model.ID == time_model_id:
            return time_model
    raise HTTPException(404, "Time model not found")

def get_process(project_id: str, adapter_id: str, process_id: str):
    adapter = get_adapter(project_id, adapter_id)
    for process in adapter.process_data:
        if process.ID == process_id:
            return process
    raise HTTPException(404, "Process not found")

def get_queue_data(project_id: str, adapter_id: str, queue_id: str):
    adapter = get_adapter(project_id, adapter_id)
    for queue_data in adapter.queue_data:
        if queue_data.ID == queue_id:
            return queue_data
    raise HTTPException(404, "Queue not found")

def get_resource(project_id: str, adapter_id: str, resource_id: str):
    adapter = get_adapter(project_id, adapter_id)
    for resource in adapter.resource_data:
        if resource.ID == resource_id:
            return resource
    raise HTTPException(
        404,
        f"Resource {resource_id} not found in adapter {adapter_id} for project {project_id}",
    )

def get_sink(project_id: str, adapter_id: str, sink_id: str):
    adapter = get_adapter(project_id, adapter_id)
    for sink in adapter.sink_data:
        if sink.ID == sink_id:
            return sink
    raise HTTPException(404, "Sink not found")

def get_source(project_id: str, adapter_id: str, source_id: str):
    adapter = get_adapter(project_id, adapter_id)
    for source in adapter.source_data:
        if source.ID == source_id:
            return source
    raise HTTPException(404, "Source not found")

def get_state(project_id: str, adapter_id: str, state_id: str):
    adapter = get_adapter(project_id, adapter_id)
    for state in adapter.state_data:
        if state.ID == state_id:
            return state
    raise HTTPException(404, "State not found")



def prepare_adapter_from_optimization(
    adapter_object: prodsys.adapters.JsonProductionSystemAdapter,
    project_id: str,
    adapter_id: str,
    solution_id: str,
):
    origin_adapter = get_adapter(project_id, adapter_id)
    adapter_object.scenario_data = origin_adapter.scenario_data
    adapter_object.ID = solution_id

    project = get_project(project_id)
    project.adapters[solution_id] = adapter_object

    runner_object = prodsys.runner.Runner(adapter=adapter_object)
    runner_object.initialize_simulation()
    if adapter_object.scenario_data and adapter_object.scenario_data.info.time_range:
        run_length = adapter_object.scenario_data.info.time_range
    else:
        run_length = 2 * 7 * 24 * 60
    runner_object.run(run_length)

    performance = runner_object.get_performance_data()
    results_database[adapter_id] = performance


def get_configuration_results_adapter_from_filesystem(
    project_id: str, adapter_id: str, solution_id: str
):
    adapter_object = prodsys.adapters.JsonProductionSystemAdapter()
    files = os.listdir(f"data/{project_id}/{adapter_id}")
    if not any(solution_id in file for file in files):
        raise HTTPException(
            404,
            f"Solution {solution_id} for adapter {adapter_id} in project {project_id} does not exist.",
        )
    file_name = next(file for file in files if solution_id in file)
    adapter_object.read_data(f"data/{project_id}/{adapter_id}/{file_name}")
    return adapter_object
