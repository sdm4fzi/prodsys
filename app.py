from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import hydra
from omegaconf import DictConfig
import uvicorn
import os

from app.routers import (
    projects,
    adapters,
    simulation,
    optimization,
    time_models,
    examples,
    performance,
    processes,
    queue,
    resources, 
    sink,
    source,
    state, 
    scenario
)

import prodsys

description = """
The prodsys API allows you to create and run production simulations and optimizations with the prodsys library as a web service. 
"""

app = FastAPI(
    title="prodsys API",
    description=description,
    version=prodsys.VERSION,
    contact={
        "name": "Sebastian Behrendt",
        "email": "sebastian.behrendt@kit.edu",
    },
    license_info={
        "name": "MIT License",
        "url": "https://mit-license.org/",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(examples.router)
app.include_router(adapters.router)
app.include_router(simulation.router)
app.include_router(optimization.router)
app.include_router(performance.router)
app.include_router(time_models.router)
app.include_router(processes.router)
app.include_router(queue.router)
app.include_router(resources.router)
app.include_router(sink.router)
app.include_router(source.router)
app.include_router(state.router)
app.include_router(scenario.router)


@app.get("/", response_model=str)
async def root():
    # return {"message": f"prodsys API v{str(prodsys.VERSION)}"}
    return "Hello World!"


@hydra.main(config_path="conf", config_name="config", version_base=None)
def prodsys_app(cfg: DictConfig) -> None:
    if os.environ.get("ROOT_PATH"):
        uvicorn.run(app, root_path=os.environ.get("ROOT_PATH"), host=cfg.fastapi.host, port=cfg.fastapi.port)
    else:
        uvicorn.run(app, host=cfg.fastapi.host, port=cfg.fastapi.port)

if __name__ == "__main__":
    prodsys_app()