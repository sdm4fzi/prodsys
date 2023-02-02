from __future__ import annotations

from enum import Enum
from typing import Literal, Union

from prodsim.data_structures.core_asset import CoreAsset

class StateTypeEnum(str, Enum):
    BreakDownState = "BreakDownState"
    ProductionState = "ProductionState"
    TransportState = "TransportState"
    SetupState = "SetupState"

class StateData(CoreAsset):
    time_model_id: str
    type: Literal[StateTypeEnum.BreakDownState, StateTypeEnum.ProductionState, StateTypeEnum.TransportState, StateTypeEnum.SetupState]

class BreakDownStateData(StateData):
    type: Literal[StateTypeEnum.BreakDownState]

class ProductionStateData(StateData):
    type: Literal[StateTypeEnum.ProductionState]

class TransportStateData(StateData):
    type: Literal[StateTypeEnum.TransportState]

class SetupStateData(StateData):
    type: Literal[StateTypeEnum.SetupState]
    origin_setup: str
    target_setup: str

STATE_DATA_UNION = Union[BreakDownStateData, ProductionStateData, TransportStateData, SetupStateData]