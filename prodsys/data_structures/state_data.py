from __future__ import annotations

from enum import Enum
from typing import Literal, Union

from prodsys.data_structures.core_asset import CoreAsset


class StateTypeEnum(str, Enum):
    BreakDownState = "BreakDownState"
    ProductionState = "ProductionState"
    TransportState = "TransportState"
    SetupState = "SetupState"
    ProcessBreakDownState = "ProcessBreakDownState"


class StateData(CoreAsset):
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
                "ID": "state_1",
                "description": "State data for state_1",
                "time_model_id": "time_model_1",
                "type": "ProductionState",
            }
        }


class BreakDownStateData(StateData):
    type: Literal[StateTypeEnum.BreakDownState]
    repair_time_model_id: str

    class Config:
        schema_extra = {
            "example": {
                "ID": "Breakdownstate_1",
                "description": "Breakdown state machine 1",
                "time_model_id": "function_time_model_5",
                "type": "BreakDownState",
                "repair_time_model_id": "function_time_model_8",
            }
        }


class ProcessBreakDownStateData(StateData):
    type: Literal[StateTypeEnum.ProcessBreakDownState]
    repair_time_model_id: str
    process_id: str

    class Config:
        schema_extra = {
            "example": {
                "ID": "ProcessBreakDownState_1",
                "description": "Process Breakdown state machine 1",
                "time_model_id": "function_time_model_7",
                "type": "ProcessBreakDownState",
                "process_id": "P1",
                "repair_time_model_id": "function_time_model_8",
            }
        }


class ProductionStateData(StateData):
    type: Literal[StateTypeEnum.ProductionState]

    class Config:
        schema_extra = {
            "example": {
                "ID": "ProductionState_1",
                "description": "Production state machine 1",
                "time_model_id": "function_time_model_1",
                "type": "ProductionState",
            }
        }


class TransportStateData(StateData):
    type: Literal[StateTypeEnum.TransportState]

    class Config:
        schema_extra = {
            "example": {
                "ID": "TransportState_1",
                "description": "Transport state machine 1",
                "time_model_id": "function_time_model_3",
                "type": "TransportState",
            }
        }


class SetupStateData(StateData):
    type: Literal[StateTypeEnum.SetupState]
    origin_setup: str
    target_setup: str

    class Config:
        schema_extra = {
            "example": {
                    "ID": "Setup_State_2",
                    "description": "Setup state machine 2",
                    "time_model_id": "function_time_model_2",
                    "type": "SetupState",
                    "origin_setup": "P2",
                    "target_setup": "P1",
            }
        }


STATE_DATA_UNION = Union[
    BreakDownStateData,
    ProductionStateData,
    TransportStateData,
    SetupStateData,
    ProcessBreakDownStateData,
]
