"""Analytics window ends at last event when nominal cap exceeds active sim time."""

import pandas as pd
import pytest

from prodsys.analytics.store import AnalyticsStore
from prodsys.util.post_processing import PostProcessor


def _minimal_production_log(max_time: float) -> pd.DataFrame:
  return pd.DataFrame(
      {
          "Time": [0.0, 10.0, max_time],
          "Resource": ["machine", "machine", "machine"],
          "State": ["S1", "S1", "S1"],
          "State Type": ["Production", "Production", "Production"],
          "Activity": ["start state", "end state", "end state"],
          "Product": ["P_0", "P_0", "P_0"],
      }
  )


def test_simulation_end_time_clamps_when_cap_far_beyond_last_event():
    df = _minimal_production_log(500.0)
    store = AnalyticsStore.from_raw(df, time_range=1000.0)
    assert store.simulation_end_time == pytest.approx(500.0)


def test_simulation_end_time_keeps_small_nominal_extension():
    """A cap slightly beyond the last event stays intentional (test fixtures)."""
    df = _minimal_production_log(80.0)
    store = AnalyticsStore.from_raw(df, time_range=100.0)
    assert store.simulation_end_time == pytest.approx(100.0)


def test_simulation_end_time_uses_configured_when_events_fill_horizon():
    df = _minimal_production_log(1000.0)
    store = AnalyticsStore.from_raw(df, time_range=1000.0)
    assert store.simulation_end_time == pytest.approx(1000.0)


def test_post_processor_resource_states_use_active_sim_time():
    df = _minimal_production_log(500.0)
    pp = PostProcessor(df_raw=df, time_range=1000.0)
    agg = pp.df_aggregated_resource_states
    resource_time = agg["resource_time"].iloc[0]
    assert resource_time == pytest.approx(500.0)
