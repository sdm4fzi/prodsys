from typing import List, Dict

from fastapi import FastAPI, HTTPException

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
)
import prodsim

app = FastAPI()

class Project(BaseModel):
    ID: str
    adapters: Dict[str, prodsim.adapters.JsonAdapter] = {}

class Result(BaseModel):
    adapter_id: str
    event_results: dict
    aggregated_results: dict

database: List[Project] = []
results_database: List[Result] = []


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


@app.get("/projects", response_model=List[Project])
async def read_projects() -> List[Project]:
    return get_projects()


@app.put("/projects/{project_id}")
async def create_project(project: Project) -> str:
    database.append(project)
    return "Sucessfully created project with ID: " + project.ID


@app.get("/projects/{project_id}", response_model=Project)
async def read_project(project_id: str) -> Project:
    return get_project(project_id)


@app.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    project = get_project(project_id)
    database.remove(project)
    return "Sucessfully deleted project with ID: " + project_id


@app.put("/projects/{project_id}/adapters")
async def create_adapter(project_id: str, adapter: prodsim.adapters.JsonAdapter):
    project = get_project(project_id)
    project.adapters.append(adapter)
    return "Sucessfully created adapter with ID: " + adapter.ID


@app.get(
    "/projects/{project_id}/adapters", response_model=Dict[str, prodsim.adapters.JsonAdapter]
)
async def read_adapters(project_id: str):
    project = get_project(project_id)
    return project.adapters


def get_adapter(project_id: str, adapter_id: str) -> prodsim.adapters.JsonAdapter:
    project = get_project(project_id)
    if adapter_id not in project.adapters:
        raise HTTPException(404, f"Adapter {adapter_id} not found in project {project_id}")
    return project.adapters[adapter_id]


@app.get(
    "/projects/{project_id}/adapters/{adapter_id}", response_model=prodsim.adapters.JsonAdapter
)
async def read_adapter(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter


@app.put("/projects/{project_id}/adapters/{adapter_id}")
async def update_adapter(project_id: str, adapter_id: str, ada: prodsim.adapters.JsonAdapter):
    project = get_project(project_id)
    project.adapters[adapter_id] = ada
    return "Sucessfully updated adapter with ID: " + adapter_id


@app.delete("/projects/{project_id}/adapters/{adapter_id}")
async def delete_adapter(project_id: str, adapter_id: str):
    project = get_project(project_id)
    adapter = get_adapter(project_id, adapter_id)
    project.adapters.pop(adapter_id)
    return "Sucessfully deleted adapter with ID: " + adapter_id


@app.get("/projects/{project_id}/adapters/{adapter_id}/run_simulation")
async def run_simulation(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    runner_object = prodsim.runner.Runner(adapter=adapter)
    runner_object.initialize_simulation()
    runner_object.run(3000)
    results_database.append(Result(adapter_id=adapter_id, event_results=runner_object.get_event_data_simulation_results_as_dict(), 
        aggregated_results=runner_object.get_aggregated_data_simulation_results()))

    return "Sucessfully ran simulation for adapter with ID: " + adapter_id

def get_result(project_id: str, adapter_id: str) -> Result:
    for result in results_database:
        if result.adapter_id == adapter_id:
            return result
    raise HTTPException(404, "Results not found")

@app.get("/projects/{project_id}/adapters/{adapter_id}/results", response_model=Result)
async def get_all_results(project_id: str, adapter_id: str):
    result = get_result(project_id, adapter_id)
    return result

@app.get("/projects/{project_id}/adapters/{adapter_id}/results/event_results", response_model=dict)
async def get_event_results(project_id: str, adapter_id: str):
    result = get_result(project_id, adapter_id)
    return result.event_results

@app.get("/projects/{project_id}/adapters/{adapter_id}/results/aggregated_results", response_model=dict)
async def get_aggregated_results(project_id: str, adapter_id: str):
    result = get_result(project_id, adapter_id)
    print(result.aggregated_results)
    return result.aggregated_results

#################### Time model data ####################



@app.get("/projects/{project_id}/adapters/{adapter_id}/time_models", response_model=List[time_model_data.TIME_MODEL_DATA])
async def read_time_models(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.time_model_data

def get_time_model(project_id: str, adapter_id: str, time_model_id: str):
    adapter = get_adapter(project_id, adapter_id)
    for time_model in adapter.time_model_data:
        if time_model.ID == time_model_id:
            return time_model
    raise HTTPException(404, "Time model not found")


@app.put("/projects/{project_id}/adapters/{adapter_id}/time_models/{time_model_id}")
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

@app.get("/projects/{project_id}/adapters/{adapter_id}/time_models/{time_model_id}", response_model=time_model_data.TIME_MODEL_DATA)
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

@app.get("/projects/{project_id}/adapters/{adapter_id}/materials", response_model=List[material_data.MaterialData])
async def read_materials(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.material_data

@app.put("/projects/{project_id}/adapters/{adapter_id}/materials/{material_id}")
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

#################### Process Data ####################

@app.get("/projects/{project_id}/adapters/{adapter_id}/materials/{material_id}", response_model=material_data.MaterialData)
async def read_material(project_id: str, adapter_id: str, material_id: str):
    material = get_material(project_id, adapter_id, material_id)
    return material

def get_process(project_id: str, adapter_id: str, process_id: str):
    adapter = get_adapter(project_id, adapter_id)
    for process in adapter.process_data:
        if process.ID == process_id:
            return process
    raise HTTPException(404, "Process not found")

@app.get("/projects/{project_id}/adapters/{adapter_id}/processes", response_model=List[processes_data.ProcessData])
async def read_processes(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.process_data

@app.put("/projects/{project_id}/adapters/{adapter_id}/processes/{process_id}")
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

@app.get("/projects/{project_id}/adapters/{adapter_id}/processes/{process_id}", response_model=processes_data.ProcessData)
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

@app.get("/projects/{project_id}/adapters/{adapter_id}/queues", response_model=List[queue_data.QueueData])
async def read_queues(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.queue_data

@app.put("/projects/{project_id}/adapters/{adapter_id}/queues/{queue_id}")
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

@app.get("/projects/{project_id}/adapters/{adapter_id}/queues/{queue_id}", response_model=queue_data.QueueData)
async def read_queue(project_id: str, adapter_id: str, queue_id: str):
    queue = get_queue_data(project_id, adapter_id, queue_id)
    return queue

####################### Resource Data ############################	

@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/resources",
    response_model=List[resource_data.RESOURCE_DATA_UNION],
)
async def read_resources(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.resource_data


def get_resource(project_id: str, adapter_id: str, resource_id: str):
    adapter = get_adapter(project_id, adapter_id)
    for resource in adapter.resource_data:
        if resource.ID == resource_id:
            return resource
    raise HTTPException(404, f"Resource {resource_id} not found in adapter {adapter_id} for project {project_id}")


@app.delete("/projects/{project_id}/adapters/{adapter_id}/resources/{resource_id}")
async def delete_resource(project_id: str, adapter_id: str, resource_id: str):
    adapter = get_adapter(project_id, adapter_id)
    resource = get_resource(project_id, adapter_id, resource_id)
    adapter.resource_data.remove(resource)
    return "Sucessfully deleted resource with ID: " + resource_id



@app.get(
    "/projects/{project_id}/adapters/{adapter_id}/resources/{resource_id}",
    response_model=resource_data.RESOURCE_DATA_UNION,
)
async def read_resource(project_id: str, adapter_id: str, resource_id: str):
    resource = get_resource(project_id, adapter_id, resource_id)
    return resource


@app.put("/projects/{project_id}/adapters/{adapter_id}/resources/{resource_id}")
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


@app.get("/projects/{project_id}/adapters/{adapter_id}/sinks", response_model=List[sink_data.SinkData])
async def read_sinks(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.sink_data

@app.put("/projects/{project_id}/adapters/{adapter_id}/sinks/{sink_id}")
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

@app.get("/projects/{project_id}/adapters/{adapter_id}/sinks/{sink_id}", response_model=sink_data.SinkData)
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

@app.get("/projects/{project_id}/adapters/{adapter_id}/sources", response_model=List[source_data.SourceData])
async def read_sources(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.source_data

@app.put("/projects/{project_id}/adapters/{adapter_id}/sources/{source_id}")
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

@app.get("/projects/{project_id}/adapters/{adapter_id}/sources/{source_id}", response_model=source_data.SourceData)
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

@app.get("/projects/{project_id}/adapters/{adapter_id}/states", response_model=List[state_data.StateData])
async def read_states(project_id: str, adapter_id: str):
    adapter = get_adapter(project_id, adapter_id)
    return adapter.state_data

@app.put("/projects/{project_id}/adapters/{adapter_id}/states/{state_id}")
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

@app.get("/projects/{project_id}/adapters/{adapter_id}/states/{state_id}", response_model=state_data.StateData)
async def read_state(project_id: str, adapter_id: str, state_id: str):
    state = get_state(project_id, adapter_id, state_id)
    return state

