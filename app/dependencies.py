import time
from typing import Dict

import os
import json

from fastapi import HTTPException
from app.backends.backend import Backend
from app.backends.in_memory import InMemoryBackend
from app.models.progress_report import ProgressReport
import prodsys
import prodsys.simulation
import prodsys.simulation.sim
from prodsys.optimization.optimizer import Optimizer
from prodsys.util.post_processing import PostProcessor

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


def get_progress_of_simulation(project_id: str, adapter_id: str) -> ProgressReport:
    if adapter_id not in runners:
        raise HTTPException(
            404,
            f"No simulation was yet started for adapter {adapter_id} in project {project_id}.",
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


def run_simulation(project_id: str, adapter_id: str, run_length: float, seed: int):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    adapter.seed = seed
    runner_object = prodsys.runner.Runner(adapter=adapter)
    runners[adapter_id] = runner_object
    runner_object.initialize_simulation()
    runner_object.run(run_length)
    performance = runner_object.get_performance_data(dynamic_data=True)
    try:
        prodsys_backend.create_performance(project_id, adapter_id, performance)
    except:
        prodsys_backend.update_performance(project_id, adapter_id, performance)
    post_processor = runner_object.get_post_processor()
    try:
        prodsys_backend.create_post_processor(project_id, adapter_id, post_processor)
    except:
        prodsys_backend.update_post_processor(project_id, adapter_id, post_processor)

def get_post_processor(project_id: str, adapter_id: str) -> PostProcessor:
    try:
        return prodsys_backend.get_post_processor(project_id, adapter_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_progress_of_optimization(optimizer: Optimizer) -> ProgressReport:
    # Get the current progress from the optimizer
    progress = optimizer.get_progress()

    total_steps = progress.total_steps
    completed_steps = progress.completed_steps

    # Calculate the ratio of completed steps
    if total_steps > 0:
        ratio_done = completed_steps / total_steps
    else:
        ratio_done = 0.0

    # Get the starting time from the optimizer (ensure you store the start time somewhere in the optimizer)
    start_time = (
        optimizer.start_time
    )  # This should be initialized when optimization starts
    current_time = time.time()  # Current time

    # Time already spent (in seconds)
    time_done = current_time - start_time

    # Estimate remaining time based on the ratio of completion
    if ratio_done > 0:
        # If we have made progress, estimate the total time and remaining time
        expected_total_time = time_done / ratio_done
        expected_time_left = expected_total_time - time_done
    else:
        # If no progress has been made, assume 0 for the remaining time (initial stage)
        expected_total_time = 0.0
        expected_time_left = 0.0

    # Round the times to two decimal places
    return ProgressReport(
        ratio_done=round(ratio_done, 2),
        time_done=round(time_done, 2),
        expected_time_left=round(expected_time_left, 2),
        expected_total_time=round(expected_total_time, 2),
    )


def prepare_adapter_from_optimization(
    adapter_object_optimized: prodsys.adapters.JsonProductionSystemAdapter,
    project_id: str,
    baseline_adapter_id: str,
    solution_id: str,
):
    prodsys_backend.delete_post_processor(project_id, baseline_adapter_id)
    origin_adapter = prodsys_backend.get_adapter(project_id, baseline_adapter_id)
    adapter_object_optimized.scenario_data = origin_adapter.scenario_data
    adapter_object_optimized.ID = solution_id

    prodsys_backend.create_adapter(project_id, adapter_object_optimized)

    project = prodsys_backend.get_project(project_id)
    project.adapters.append(adapter_object_optimized)

    runner_object = prodsys.runner.Runner(adapter=adapter_object_optimized)
    runner_object.initialize_simulation()
    if (
        adapter_object_optimized.scenario_data
        and adapter_object_optimized.scenario_data.info.time_range
    ):
        run_length = adapter_object_optimized.scenario_data.info.time_range
    else:
        run_length = 2 * 7 * 24 * 60
    runner_object.run(run_length)

    post_processor = runner_object.get_post_processor()
    try:
        prodsys_backend.create_post_processor(
            project_id, baseline_adapter_id, post_processor
        )
    except:
        prodsys_backend.update_post_processor(
            project_id, baseline_adapter_id, post_processor
        )

    performance = runner_object.get_performance_data(dynamic_data=True)
    project.performances[adapter_object_optimized.ID] = performance
    try:
        prodsys_backend.create_performance(project_id, baseline_adapter_id, performance)
    except:
        prodsys_backend.update_performance(project_id, baseline_adapter_id, performance)

    prodsys_backend.update_project(project_id, project)