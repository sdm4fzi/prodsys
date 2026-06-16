"""Instant same-timestamp start+end pairs must not leave phantom open intervals."""

import pandas as pd
import pytest

from prodsys.analytics import AnalyticsStore


def test_instant_breakdown_large_pair_does_not_stay_open():
    """MQTT ingest can emit end+start at the same time; builder must not keep breakdown open."""
    t = 100.0
    df = pd.DataFrame(
        [
            {
                "Time": t,
                "Resource": "M04",
                "Activity": "end state",
                "State": "breakdown_large",
                "State Type": "Breakdown",
                "Product": None,
            },
            {
                "Time": t,
                "Resource": "M04",
                "Activity": "start state",
                "State": "breakdown_large",
                "State Type": "Breakdown",
                "Product": None,
            },
            {
                "Time": t,
                "Resource": "M04",
                "Activity": "start state",
                "State": "alarm_401",
                "State Type": "Breakdown",
                "Product": None,
            },
            {
                "Time": t + 10.0,
                "Resource": "M04",
                "Activity": "end state",
                "State": "alarm_401",
                "State Type": "Breakdown",
                "Product": None,
            },
        ]
    )
    store = AnalyticsStore.from_raw(df, time_range=200.0)
    assert store.builder.num_open == 0

    rs = store.resource_states(t_from=0.0, t_to=200.0)
    m04 = rs[rs["Resource"] == "M04"]
    ud = m04[m04["Time_type"] == "UD"]["percentage"].sum()
    assert ud < 50.0
    assert m04["percentage"].sum() == pytest.approx(100.0, abs=1.0)
