from typing import Annotated, Dict, Optional
from pydantic import BaseModel, Field

from prodsys.adapters.json_adapter import JsonProductionSystemAdapter


AdapterHash = Annotated[
    str, Field(..., description="MD5 hash identifier of the individual configuration")
]
AdapterId = Annotated[str, Field(..., description="ID of the adapter")]
GenerationIndex = Annotated[str, Field(..., description="Index of the generation")]

class SolutionMetadata(BaseModel):
    generation: GenerationIndex
    ID: AdapterId

OptimizationSolutionDict = dict[AdapterHash, SolutionMetadata]  # Dict of adapter ID to hash

class OptimizationProgress(BaseModel):
    total_steps: int = Field(0, description="Total number of steps in the optimization process")
    completed_steps: int = Field(0, description="Number of steps completed")
    hashes: dict[AdapterId, AdapterHash] = Field({}, description="Mapping of adapter ID to hash")

class OptimizationSolutions(BaseModel):
    current_generation: str = Field("0", description="Current generation index")
    hashes: OptimizationSolutionDict = Field({}, description="Mapping of adapter ID to hash")


class FitnessData(BaseModel):
    agg_fitness: float = Field(..., description="Aggregated fitness value")
    fitness: list[float] = Field(..., description="List of fitness components")
    objective_names: Optional[list[str]] = Field(None, description="List of objective names for the fitness components")
    time_stamp: float = Field(..., description="Timestamp of the fitness data in seconds since start of optimization")
    hash: AdapterHash
    production_system: Optional[JsonProductionSystemAdapter] = Field(None, description="Production system configuration")
    event_log_dict: Optional[dict] = Field(None, description="Event log dictionary")


FitnessEntry = Annotated[dict[AdapterId, FitnessData], Field(..., description="Mapping of adapter ID to its fitness data")]
OptimizationResults = Annotated[dict[GenerationIndex, FitnessEntry], Field(..., description="Mapping of generation index to its fitness data")]

def get_empty_optimization_results() -> OptimizationResults:
    return {"0": {}}
