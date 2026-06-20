"""
Runtime-only standby state loggers for explicit Blocked / Starved / Idle / WaitingForTransport
intervals in the event log.

External inference (outside this package) can reconstruct the same categories from
Loading/Unloading end-state events (Origin/Target location) plus queue capacities
from port_data.QueueData — see module docstring in standby_logging.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from prodsys.simulation.state import StateInfo, StateTypeEnum

if TYPE_CHECKING:
    from prodsys.simulation.sim import Environment


class StandbyStates:
    """Holds StateInfo objects for runtime standby categories (not configured in state_data)."""

    def __init__(self, env: Environment, resource_id: str):
        self.env = env
        self.resource_id = resource_id
        self.blocked = StateInfo(ID=f"{resource_id}_blocked", resource_ID=resource_id)
        self.starved = StateInfo(ID=f"{resource_id}_starved", resource_ID=resource_id)
        self.idle = StateInfo(ID=f"{resource_id}_idle", resource_ID=resource_id)
        self.waiting_for_transport = StateInfo(
            ID=f"{resource_id}_waiting_for_transport", resource_ID=resource_id
        )
        self._idle_active_type: Optional[StateTypeEnum] = None

    def info_for(self, state_type: StateTypeEnum) -> StateInfo:
        return {
            StateTypeEnum.blocked: self.blocked,
            StateTypeEnum.starved: self.starved,
            StateTypeEnum.idle: self.idle,
            StateTypeEnum.waiting_for_transport: self.waiting_for_transport,
        }[state_type]

    def all_state_infos(self) -> list[StateInfo]:
        return [self.blocked, self.starved, self.idle, self.waiting_for_transport]
