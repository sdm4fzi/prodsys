"""
Helpers for logging explicit standby resource states at SimPy wait points.

Inference outside prodsys (real event logs) can derive the same categories by:
  1. Rebuilding per-queue WIP from Loading/Unloading ``end state`` rows
     (Origin location / Target location), as in PostProcessor._compute_wip_per_resource.
  2. Reading queue capacities from port_data.QueueData (capacity 0 = infinite).
  3. Classifying resource idle windows:
       - Blocked: available, output queue at capacity
       - Starved: job accepted, input queue empty for required item
       - Idle / WaitingForTransport: available, no controller requests

Logged attribution uses queue IDs in Origin/Target location columns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Generator

from prodsys.simulation.state import StateTypeEnum

if TYPE_CHECKING:
    from prodsys.simulation import port, resources


def log_starved_around_get(
    resource: resources.Resource,
    queue: port.Queue,
    item_id: str,
) -> Generator:
    """Log Starved while waiting for item_id to appear in queue."""
    info = resource.standby_states.info_for(StateTypeEnum.starved)
    waiting = item_id not in queue.items
    if waiting:
        info._origin_ID = queue.data.ID
        info.log_start_state(resource.env.now, resource.env.now, StateTypeEnum.starved)
    yield from queue.get(item_id)
    if waiting:
        info.log_end_state(resource.env.now, StateTypeEnum.starved)


def log_blocked_around_put(
    resource: resources.Resource,
    queue: port.Queue,
    item,
) -> Generator:
    """Log Blocked while put() waits for free space on a full queue."""
    info = resource.standby_states.info_for(StateTypeEnum.blocked)
    will_wait = queue._pending_put == 0 and queue.is_full
    if will_wait:
        info._target_ID = queue.data.ID
        info.log_start_state(resource.env.now, resource.env.now, StateTypeEnum.blocked)
    yield from queue.put(item)
    if will_wait:
        info.log_end_state(resource.env.now, StateTypeEnum.blocked)
