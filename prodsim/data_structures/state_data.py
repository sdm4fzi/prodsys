from __future__ import annotations

from enum import Enum
from typing import Literal

from .core_asset import CoreAsset

class StateTypeEnum(str, Enum):
    BreakDownState = "BreakDownState"
    ProductionState = "ProductionState"
    TransportState = "TransportState"

class StateData(CoreAsset):
    time_model_id: str
    type: Literal[StateTypeEnum.BreakDownState, StateTypeEnum.ProductionState, StateTypeEnum.TransportState]

class BreakDownStateData(StateData):
    type: Literal[StateTypeEnum.BreakDownState]

class ProductionStateData(StateData):
    type: Literal[StateTypeEnum.ProductionState]

class TransportStateData(StateData):
    type: Literal[StateTypeEnum.TransportState]