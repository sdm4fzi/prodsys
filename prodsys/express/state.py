"""
The `state` module contains the `prodsys.express` classes to represent the states that resources 
can be in during a simulation, besides processing and standby.

The following states are possible:

- `Breakdown`: A state that makes a resource unavailable for a certain time.
- `ProcessBreakdown`: A state that makes a process unavailable for a certain time but other processes can still be performed.
- `Setup`: A state that represents the time needed to change the process of a resource.	    

"""
from __future__ import annotations

from typing import List, Optional, Union
from uuid import uuid1

from abc import ABC

from pydantic import Field
from pydantic.dataclasses import dataclass

from prodsys.express import core, time_model

from prodsys.models import state_data



@dataclass
class State(ABC):
    """
    Abstract base class to represents a state.

    Args:
        time_model (time_model.TIME_MODEL_UNION): Time model of the state.
    """

    time_model: time_model.TIME_MODEL_UNION

@dataclass
class BreakDownState(State, core.ExpressObject):
    """
    Class that represents a breakdown state.

    Args:
        time_model (time_model.TIME_MODEL_UNION): Breakdwon occurence time model of the state.
        repair_time_model (time_model.TIME_MODEL_UNION): Reapit time model of the state.    
        ID (str): ID of the state.

    Attributes:
        type (state_data.StateTypeEnum): Type of the state. Equals to state_data.StateTypeEnum.BreakDownState.

    Examples:
        Breakdown state with a function time model:
        ``` py
        import prodsys.express as psx
        breakdown_time_model = psx.FunctionTimeModel(
            distribution_function="normal",
            location=10.0,
            scale=5.0,
        )
        repair_time_model = psx.FunctionTimeModel(
            distribution_function="normal",
            location=10.0,
            scale=5.0,
        )
        psx.BreakDownState(
            time_model=breakdown_time_model,
            reapit_time_model=repair_time_model
        )
        ```
    """
    repair_time_model: time_model.TIME_MODEL_UNION
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))
    type: state_data.StateTypeEnum = Field(default=state_data.StateTypeEnum.BreakDownState, init=False)

    def to_model(self) -> state_data.BreakDownStateData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            state_data.BreakDownStateData: Data object of the express object.
        """
        return state_data.BreakDownStateData(
            ID=self.ID,
            description="",
            time_model_id=self.time_model.ID,
            type=self.type,
            repair_time_model_id=self.repair_time_model.ID
        )
    
@dataclass
class ProcessBreakdownState(State, core.ExpressObject):
    """
    Class that represents a process breakdown state.

    Args:
        time_model (time_model.TIME_MODEL_UNION): Breakdwon occurence time model of the state.
        repair_time_model (time_model.TIME_MODEL_UNION): Reapit time model of the state.
        process (process.PROCESS_UNION): Process that is broken down due to this breakdown state.
        ID (str): ID of the state.

    Attributes:
        type (state_data.StateTypeEnum): Type of the state. Equals to state_data.StateTypeEnum.ProcessBreakDownState.

    Examples:
        Process breakdown state with a normally distributed repair and breakdwon time for an examplary process:
       
        ``` py
        import prodsys.express as psx
        breakdown_time_model = psx.FunctionTimeModel(
            distribution_function="normal",
            location=100.0,
            scale=23.0,
        )
        repair_time_model = psx.FunctionTimeModel(
            distribution_function="normal",
            location=10.0,
            scale=5.0,
        )
        process_time_model = psx.FunctionTimeModel(
            distribution_function="normal",
            location=10.0,
            scale=5.0,
        )
        process = psx.ProdutionProcess(
            time_model=process_time_model
        )
        psx.ProcessBreakDownState(
            time_model=breakdown_time_model,
            repair_time_model=repair_time_model,
            process=process
        )
        ```
    """
    repair_time_model: time_model.TIME_MODEL_UNION
    process: process.PROCESS_UNION
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))
    type: state_data.StateTypeEnum = Field(default=state_data.StateTypeEnum.ProcessBreakDownState, init=False)

    def to_model(self) -> state_data.ProcessBreakDownStateData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            state_data.ProcessBreakDownStateData: Data object of the express object.
        """
        return state_data.ProcessBreakDownStateData(
            ID=self.ID,
            description="",
            time_model_id=self.time_model.ID,
            type=self.type,
            repair_time_model_id=self.repair_time_model.ID,
            process_id=self.process.ID
        )

@dataclass
class SetupState(State, core.ExpressObject):
    """
    Class that represents a setup state.

    Args:
        time_model (time_model.TIME_MODEL_UNION): Time model of the state.
        origin_setup (process.Process): Process that is the origin of the setup.
        target_setup (process.Process): Process that is the target of the setup.
        ID (str): ID of the state.

    Attributes:
        type (state_data.StateTypeEnum): Type of the state. Equals to state_data.StateTypeEnum.SetupState.

    Examples:
        Setup state with a function time model:
        ``` py
        import prodsys.express as psx
        setup_time_model = psx.FunctionTimeModel(
            distribution_function="normal",
            location=10.0,
            scale=5.0,
        )
        dummy_process_time_model = psx.FunctionTimeModel(
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        dummy_origin_process = psx.ProductionProcess(
            time_model=dummy_process_time_model
        )
        dummy_target_process = psx.ProductionProcess(
            time_model=dummy_process_time_model
        )
        psx.SetupState(
            time_model=setup_time_model,
            origin_setup=dummy_origin_process,
            target_setup=dummy_target_process
        )
        ```
    """
    origin_setup: process.PROCESS_UNION
    target_setup: process.PROCESS_UNION
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))
    type: state_data.StateTypeEnum = Field(default=state_data.StateTypeEnum.SetupState, init=False)

    def to_model(self) -> state_data.SetupStateData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            state_data.SetupStateData: Data object of the express object.
        """
        return state_data.SetupStateData(
            ID=self.ID,
            description="",
            time_model_id=self.time_model.ID,
            type=self.type,
            origin_setup=self.origin_setup.ID,
            target_setup=self.target_setup.ID
        )
    
STATE_UNION = Union[BreakDownState, ProcessBreakdownState, SetupState]
from prodsys.express import process