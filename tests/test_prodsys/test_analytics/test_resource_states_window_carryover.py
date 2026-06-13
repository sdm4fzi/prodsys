"""Windowed resource_states must include still-open intervals from before t_from."""

import pandas as pd
import pytest

from prodsys.analytics import AnalyticsStore
from prodsys.simulation.state import StateTypeEnum


def _start_state(resource: str, t: float, state_type: str) -> dict:
    return {
        "Time": t,
        "Resource": resource,
        "Activity": "start state",
        "State": f"{resource}_state",
        "State Type": state_type,
        "Product": None,
    }


def test_resource_states_includes_open_non_scheduled_before_window():
    """NS started before the query window should count for the whole shift."""
    df = pd.DataFrame(
        [
            _start_state("M01", 0.0, StateTypeEnum.non_scheduled.value),
            _start_state("M02", 50.0, StateTypeEnum.production.value),
            {
                "Time": 80.0,
                "Resource": "M02",
                "Activity": "end state",
                "State": "M02_state",
                "State Type": StateTypeEnum.production.value,
                "Product": None,
            },
        ]
    )
    store = AnalyticsStore.from_raw(df, time_range=100.0)

    rs = store.resource_states(t_from=60.0, t_to=100.0)
    m01 = rs[rs["Resource"] == "M01"].set_index("Time_type")["time_increment"].to_dict()
    assert m01.get("NS", 0.0) == pytest.approx(40.0)
    assert "M01" in set(rs["Resource"])

    # Without open-interval carry-over M01 would be absent from the window.
    broken = store.intervals
    broken = broken[(broken["t_end"] > 60.0) & (broken["t_start"] < 100.0)]
    assert broken[broken["entity_id"] == "M01"].empty
