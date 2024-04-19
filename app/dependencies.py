import time
from typing import Dict, List, Optional

import os

from fastapi import HTTPException
from torch import exp
from app.backends.backend import Backend
from app.backends.in_memory import InMemoryBackend
from app.models.progress_report import ProgressReport
import prodsys
from prodsys.models import performance_data
import prodsys.simulation
import prodsys.simulation.sim

from .models.project import Project

import logging
logger = logging.getLogger(__name__)

def get_backend() -> Backend:
    backend_name = os.getenv("PRODSYS_BACKEND") or "in_memory"
    if backend_name == "in_memory":
        logger.info("Using in-memory backend")
        return InMemoryBackend()
    if backend_name == "mongo":
        logger.info("Using MongoDB backend")
        raise NotImplementedError("MongoDB backend not implemented")
    else:
        raise Exception(f"Backend {backend_name} not possible to use for prodsys API.")


prodsys_backend = get_backend()
runners: Dict[str, prodsys.runner.Runner] = {}

def get_backend() -> Backend:
    return prodsys_backend


def get_progress_of_simulation(project_id: str, adapter_id: str) -> ProgressReport:
    if adapter_id not in runners:
        raise HTTPException(
            404, f"No simulation was yet started for adapter {adapter_id} in project {project_id}."
        )
    steps_done = runners[adapter_id].env.pbar.n
    steps_total = runners[adapter_id].env.pbar.total
    time_done = time.time() - runners[adapter_id].env.pbar.start_t

    ratio_done = steps_done / steps_total
    expected_total_time = time_done / ratio_done
    expected_time_left = expected_total_time - time_done

    return ProgressReport(
        ratio_done=ratio_done,
        time_done=round(time_done, 2),
        expected_time_left=round(expected_time_left, 2),
        expected_total_time=round(expected_total_time, 2),
    )


def get_progress_of_optimization(project_id: str, adapter_id: str) -> float:
    # TODO: implement function that returns progress of optimization
    return 0.5

def run_simulation(project_id: str, adapter_id: str, run_length: float, seed: int):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    adapter.seed = seed
    runner_object = prodsys.runner.Runner(adapter=adapter)
    runners[adapter_id] = runner_object
    runner_object.initialize_simulation()
    runner_object.run(run_length)
    performance = runner_object.get_performance_data()
    try:
        prodsys_backend.create_performance(project_id, adapter_id, performance)
    except:
        prodsys_backend.update_performance(project_id, adapter_id, performance)

def get_time_model_from_backend(project_id: str, adapter_id: str, time_model_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for time_model in adapter.time_model_data:
        if time_model.ID == time_model_id:
            return time_model
    raise HTTPException(404, "Time model not found")

def get_process_from_backend(project_id: str, adapter_id: str, process_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for process in adapter.process_data:
        if process.ID == process_id:
            return process
    raise HTTPException(404, "Process not found")

def get_queue_from_backend(project_id: str, adapter_id: str, queue_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for queue_data in adapter.queue_data:
        if queue_data.ID == queue_id:
            return queue_data
    raise HTTPException(404, "Queue not found")

def get_resource_from_backend(project_id: str, adapter_id: str, resource_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for resource in adapter.resource_data:
        if resource.ID == resource_id:
            return resource
    raise HTTPException(
        404,
        f"Resource {resource_id} not found in adapter {adapter_id} for project {project_id}",
    )

def get_sink_from_backend(project_id: str, adapter_id: str, sink_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for sink in adapter.sink_data:
        if sink.ID == sink_id:
            return sink
    raise HTTPException(404, "Sink not found")

def get_product_from_backend(project_id: str, adapter_id: str, product_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for product in adapter.product_data:
        if product.ID == product_id:
            return product
    raise HTTPException(404, "Product not found")

def get_source_from_backend(project_id: str, adapter_id: str, source_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for source in adapter.source_data:
        if source.ID == source_id:
            return source
    raise HTTPException(404, "Source not found")

def get_state_from_backend(project_id: str, adapter_id: str, state_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
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
    # TODO: use backend to save and retrieve data here...
    origin_adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    adapter_object.scenario_data = origin_adapter.scenario_data
    adapter_object.ID = solution_id

    project = prodsys_backend.get_project(project_id)
    project.adapters[solution_id] = adapter_object

    runner_object = prodsys.runner.Runner(adapter=adapter_object)
    runner_object.initialize_simulation()
    if adapter_object.scenario_data and adapter_object.scenario_data.info.time_range:
        run_length = adapter_object.scenario_data.info.time_range
    else:
        run_length = 2 * 7 * 24 * 60
    runner_object.run(run_length)

    performance = runner_object.get_performance_data()
    try:
        prodsys_backend.create_performance(project_id, adapter_id, performance)
    except:
        prodsys_backend.update_performance(project_id, adapter_id, performance)


def get_configuration_results_adapter_from_filesystem(
    project_id: str, adapter_id: str, solution_id: str
):
    # TODO: use backend to save and retrieve data here...
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
