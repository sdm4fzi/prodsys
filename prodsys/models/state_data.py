"""
The `state_data` module contains the `prodsys.models` classes to represent the states that resources 
can be in during a simulation.

The following states are possible:

- `BreakDownStateData`: A state that makes a resource unavailable for a certain time.
- `ProcessBreakDownStateData`: A state that makes a process unavailable for a certain time but other processes can still be performed.
- `SetupStateData`: A state that represents the time needed to change the process of a resource.
- `ProductionStateData`: A state that represents the time needed to process a product.
- `TransportStateData`: A state that represents the time needed to transport a product.	    
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Union

from prodsys.models.core_asset import CoreAsset


class StateTypeEnum(str, Enum):
    """
    Enum that represents the different kind of states.

    - BreakDownState: A state that makes a resource unavailable for a certain time.
    - ProductionState: A state that represents the time needed to process a product.
    - TransportState: A state that represents the time needed to transport a product.
    - SetupState: A state that represents the time needed to change the process of a resource.
    - ProcessBreakDownState: A state that makes a process unavailable for a certain time but other processes can still be performed.
    """

    BreakDownState = "BreakDownState"
    ProductionState = "ProductionState"
    TransportState = "TransportState"
    SetupState = "SetupState"
    ProcessBreakDownState = "ProcessBreakDownState"


class StateData(CoreAsset):
    """
    Class that represents a state.

    Args:
        ID (str): ID of the state.
        description (str): Description of the state.
        time_model_id (str): Time model ID of the state.
        type (StateTypeEnum): Type of the state.
    """

    time_model_id: str
    type: Literal[
        StateTypeEnum.BreakDownState,
        StateTypeEnum.ProductionState,
        StateTypeEnum.TransportState,
        StateTypeEnum.SetupState,
    ]

    class Config:
        schema_extra = {
            "example": {
                "summary": "State",
                "value": {
                    "ID": "state_1",
                    "description": "State data for state_1",
                    "time_model_id": "time_model_1",
                    "type": "ProductionState",
                },
            }
        }


class BreakDownStateData(StateData):
    """
    Class that represents a breakdown state.

    Args:
        ID (str): ID of the state.
        description (str): Description of the state.
        time_model_id (str): Time model ID of the state. Specifies the time interval between breakdowns.
        type (StateTypeEnum): Type of the state.
        repair_time_model_id (str): Time model ID of the repair time.

    Examples:
        Breakdown state with a function time model:
        ``` py  
        import prodsys
        prodsys.state_data.BreakDownStateData(
            ID="Breakdownstate_1",
            description="Breakdown state machine 1",
            time_model_id="function_time_model_5",
            repair_time_model_id="function_time_model_8",
        )
        ```
    """

    type: Literal[StateTypeEnum.BreakDownState]
    repair_time_model_id: str

    def __hash__(self):
        return hash((self.time_model_id, self.repair_time_model_id))
    
    class Config:
        schema_extra = {
            "example": {
                "summary": "Breakdown state",
                "value": {
                    "ID": "Breakdownstate_1",
                    "description": "Breakdown state machine 1",
                    "time_model_id": "function_time_model_5",
                    "type": "BreakDownState",
                    "repair_time_model_id": "function_time_model_8",
                },
            }
        }


class ProcessBreakDownStateData(StateData):
    """
    Class that represents a process breakdown state. It is a breakdown state that is connected to a process. Other processes can still be executed while the process breakdown state is activen.

    Args:
        ID (str): ID of the state.
        description (str): Description of the state.
        time_model_id (str): Time model ID of the state.
        type (StateTypeEnum): Type of the state.
        repair_time_model_id (str): Time model ID of the repair time.
        process_id (str): ID of the process that is broken down.

    Examples:
        Process breakdown state with a function time model:
        ``` py
        import prodsys
        prodsys.state_data.ProcessBreakDownStateData(
            ID="ProcessBreakDownState_1",
            description="Process Breakdown state machine 1",
            time_model_id="function_time_model_7",
            repair_time_model_id="function_time_model_8",
            process_id="P1",
        )
        ```
    """

    type: Literal[StateTypeEnum.ProcessBreakDownState]
    repair_time_model_id: str
    process_id: str

    class Config:
        schema_extra = {
            "example": {
                "summary": "Process breakdown state",
                "value": {
                    "ID": "ProcessBreakDownState_1",
                    "description": "Process Breakdown state machine 1",
                    "time_model_id": "function_time_model_7",
                    "type": "ProcessBreakDownState",
                    "process_id": "P1",
                    "repair_time_model_id": "function_time_model_8",
                },
            }
        }


class ProductionStateData(StateData):
    """
    Class that represents a production state. By undergoing a production state, the product is processed and continues its process model. Production states don't have to be initialized because they are automatically created when a process is added to a resource.

    Args:
        ID (str): ID of the state.
        description (str): Description of the state.
        time_model_id (str): Time model ID of the state.
        type (StateTypeEnum): Type of the state.

    """

    type: Literal[StateTypeEnum.ProductionState]

    class Config:
        schema_extra = {
            "example": {
                "summary": "Production state",
                "value": {
                    "ID": "ProductionState_1",
                    "description": "Production state machine 1",
                    "time_model_id": "function_time_model_1",
                    "type": "ProductionState",
                },
            }
        }


class TransportStateData(StateData):
    """
    Class that represents a transport state. By undergoing a transport state, the product is transported and its position is changed. Transport states don't have to be initialized because they are automatically created when a transport process is added to a resource.

    Args:
        ID (str): ID of the state.
        description (str): Description of the state.
        time_model_id (str): Time model ID of the state.
        type (StateTypeEnum): Type of the state.
    """

    type: Literal[StateTypeEnum.TransportState]

    class Config:
        schema_extra = {
            "example": {
                "summary": "Transport state",
                "value": {
                    "ID": "TransportState_1",
                    "description": "Transport state machine 1",
                    "time_model_id": "function_time_model_3",
                    "type": "TransportState",
                },
            }
        }


class SetupStateData(StateData):
    """
    Class that represents a setup state. By undergoing a setup state, the process is setup.

    Args:
        ID (str): ID of the state.
        description (str): Description of the state.
        time_model_id (str): Time model ID of the state.
        type (StateTypeEnum): Type of the state.
        origin_setup (str): ID of the origin process for the setup.
        target_setup (str): ID of the target process for the setup.

    Examples:
        Setup state with a function time model:
        ``` py
        import prodsys
        prodsys.state_data.SetupStateData(
            ID="Setup_State_2",
            description="Setup state machine 2",
            time_model_id="function_time_model_2",
            origin_setup="P2",
            target_setup="P1",
        )
        ```
    """

    type: Literal[StateTypeEnum.SetupState]
    origin_setup: str
    target_setup: str

    class Config:
        schema_extra = {
            "example": {
                "summary": "Setup state",
                "value": {
                    "ID": "Setup_State_2",
                    "description": "Setup state machine 2",
                    "time_model_id": "function_time_model_2",
                    "type": "SetupState",
                    "origin_setup": "P2",
                    "target_setup": "P1",
                },
            }
        }


STATE_DATA_UNION = Union[
    BreakDownStateData,
    ProductionStateData,
    TransportStateData,
    SetupStateData,
    ProcessBreakDownStateData,
]
