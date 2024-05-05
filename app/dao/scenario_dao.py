from typing import List
from fastapi import HTTPException

from prodsys.models import scenario_data
from app.dependencies import prodsys_backend
from prodsys.models.performance_indicators import KPIEnum


def get(project_id: str, adapter_id: str) -> scenario_data.ScenarioData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(
            404,
            f"Scenario for adapter with ID {adapter_id} not found. Create the scenario data at first.",
        )
    return adapter.scenario_data


def update(
    project_id: str,
    adapter_id: str,
    scenario: scenario_data.ScenarioData,
) -> scenario_data.ScenarioData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    adapter.scenario_data = scenario
    prodsys_backend.update_adapter(project_id, adapter_id, adapter)
    return scenario


def delete(project_id: str, adapter_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    if not adapter.scenario_data:
        raise HTTPException(
            404,
            f"Scenario for adapter with ID {adapter_id} not found. Create the scenario data at first.",
        )
    adapter.scenario_data = None
    prodsys_backend.update_adapter(project_id, adapter_id, adapter)


def get_constraints(
    project_id: str, adapter_id: str
) -> scenario_data.ScenarioConstrainsData:
    scenario = get(project_id, adapter_id)
    return scenario.constraints


def update_constraints(
    project_id: str,
    adapter_id: str,
    scenario_constraints: scenario_data.ScenarioConstrainsData,
) -> scenario_data.ScenarioData:
    scenario = get(project_id, adapter_id)
    scenario.constraints = scenario_constraints
    return update(project_id, adapter_id, scenario)


def get_options(project_id: str, adapter_id: str) -> scenario_data.ScenarioOptionsData:
    scenario = get(project_id, adapter_id)
    return scenario.options


def update_options(
    project_id: str,
    adapter_id: str,
    scenario_options: scenario_data.ScenarioOptionsData,
) -> scenario_data.ScenarioData:
    scenario = get(project_id, adapter_id)
    scenario.options = scenario_options
    return update(project_id, adapter_id, scenario)


def get_info(project_id: str, adapter_id: str) -> scenario_data.ScenarioInfoData:
    scenario = get(project_id, adapter_id)
    return scenario.info


def update_info(
    project_id: str, adapter_id: str, scenario_info: scenario_data.ScenarioInfoData
) -> scenario_data.ScenarioData:
    scenario = get(project_id, adapter_id)
    scenario.info = scenario_info
    return update(project_id, adapter_id, scenario)


def get_objectives(project_id: str, adapter_id: str) -> List[scenario_data.Objective]:
    scenario = get(project_id, adapter_id)
    return scenario.objectives


def update_objectives(
    project_id: str, adapter_id: str, objectives: List[scenario_data.Objective]
) -> scenario_data.ScenarioData:
    scenario = get(project_id, adapter_id)
    scenario.objectives = objectives
    return update(project_id, adapter_id, scenario)


def add_objective(
    project_id: str, adapter_id: str, objective: scenario_data.Objective
) -> scenario_data.ScenarioData:
    scenario = get(project_id, adapter_id)
    if not objective.name in [
        KPIEnum.COST,
        KPIEnum.THROUGHPUT,
        KPIEnum.THROUGHPUT,
        KPIEnum.WIP,
    ]:
        raise HTTPException(
            404,
            f"Only the objectives Cost, throughput, wip or throughput time are currently supported for optimization. {objective.name} is not allowed.",
        )
    if any(
        objective.name == existing_objective.name
        for existing_objective in scenario.objectives
    ):
        raise HTTPException(
            404,
            f"The objective with name {objective.name} already exists. Try updating it.",
        )
    scenario.objectives.append(objective)
    return update(project_id, adapter_id, scenario)


def update_objective(
    project_id: str, adapter_id: str, objective: scenario_data.Objective
) -> scenario_data.ScenarioData:
    scenario = get(project_id, adapter_id)
    if not objective.name in [
        KPIEnum.COST,
        KPIEnum.THROUGHPUT,
        KPIEnum.THROUGHPUT,
        KPIEnum.WIP,
    ]:
        raise HTTPException(
            404,
            f"Only the objectives Cost, throughput, wip or throughput time are currently supported for optimization. {objective.name} is not allowed.",
        )
    for idx, existing_objective in enumerate(scenario.objectives):
        if objective.name == existing_objective.name:
            scenario.objectives[idx] = objective
            return update(project_id, adapter_id, scenario)
    HTTPException(
        404,
        f"Objective with name {objective.name} not found for scenario of adapter {adapter_id}.",
    )


def delete_objective(
    project_id: str, adapter_id: str, objective_name: KPIEnum
) -> scenario_data.ScenarioData:
    scenario = get(project_id, adapter_id)
    for idx, objective in enumerate(scenario.objectives):
        if objective.name == objective_name:
            scenario.objectives.pop(idx)
            return update(project_id, adapter_id, scenario)
    HTTPException(
        404,
        f"Objective with name {objective_name} not found for scenario of adapter {adapter_id}.",
    )
