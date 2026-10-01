"""Throughput-time distribution plot works without ``figure_factory.create_distplot``.

plotly 7 removed ``create_distplot``; the plot draws its own KDE curves now.
"""

from types import SimpleNamespace

import pandas as pd

from prodsys.util import kpi_visualization


def test_throughput_time_distribution_plot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    df = pd.DataFrame(
        {
            "Product_type": ["A"] * 4 + ["B"] * 3 + ["C"] + ["D"] * 2,
            # C: one sample, D: identical samples -> both skipped
            "Throughput_time": [1.0, 2.0, 2.5, 4.0, 3.0, 3.5, 5.0, 7.0, 2.0, 2.0],
        }
    )
    html = kpi_visualization.plot_throughput_time_distribution(
        SimpleNamespace(df_throughput=df), return_html=True
    )
    assert html and "Probability Density" in html
    assert (tmp_path / "plots" / "throughput_time_distribution.html").exists()


def test_throughput_time_distribution_plot_without_valid_groups(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    df = pd.DataFrame({"Product_type": ["A", "B", "B"], "Throughput_time": [1.0, 2.0, 2.0]})
    assert (
        kpi_visualization.plot_throughput_time_distribution(
            SimpleNamespace(df_throughput=df), return_html=True
        )
        is None
    )
