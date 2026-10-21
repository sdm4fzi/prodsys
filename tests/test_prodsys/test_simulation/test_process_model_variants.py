"""``ProcessModelData.resource_variants``: resource-specific steps of a process model.

The product requests ``pm_a`` (manual 10 s + automatic 20 s) on station A.
With ``resource_variants={"A": "pm_a_fast"}`` station A executes its own
variant (manual 10 s + automatic 5 s) while matching, routing and the
schedule keep referring to ``pm_a``.
"""

from __future__ import annotations

import pytest

from prodsys.models.order_data import OrderData
from prodsys.models.processes_data import ProcessModelData
from prodsys.models.production_system_data import ProductionSystemData
from prodsys.simulation import runner

from tests.test_prodsys.test_simulation.test_schedule_admission import _ev, _tm, _tray_line


def _line(variants: dict[str, str]) -> ProductionSystemData:
    data = _tray_line().model_dump()
    data["time_model_data"].append(_tm("tm_a_auto_fast", 5.0))
    data["process_data"] += [
        {"ID": "a_auto_fast", "description": "", "time_model_id": "tm_a_auto_fast", "type": "ProductionProcesses"},
        {"ID": "pm_a", "description": "", "type": "ProcessModels",
         "adjacency_matrix": {"a_manual": ["a_auto"], "a_auto": []}, "resource_variants": variants},
        {"ID": "pm_a_fast", "description": "", "type": "ProcessModels",
         "adjacency_matrix": {"a_manual": ["a_auto_fast"], "a_auto_fast": []}},
    ]
    for resource in data["resource_data"]:
        if resource["ID"] == "A":
            resource["process_ids"] = ["a_manual", "a_auto", "a_auto_fast", "pm_a", "pm_a_fast"]
            resource["process_capacities"] = [1] * 5
    data["product_data"][0]["processes"] = {"pm_a": ["b_auto"], "b_auto": []}
    data["order_data"] = [
        OrderData(ID="O1", ordered_products=[{"product_type": "P", "quantity": 1}],
                  order_time=0.0, release_time=0.0, due_time=1e5, priority=1)
    ]
    ps = ProductionSystemData(**data)
    ps.schedule = [_ev(0, "A", "pm_a", "P_0", "O1")]
    return ps


def _run(ps: ProductionSystemData):
    sim = runner.Runner(production_system_data=ps)
    sim.initialize_simulation()
    sim.run_until_complete(time_range_max=5000)
    assert len(sim.product_factory.finished_products) == 1
    events = sim.event_logger.get_data_as_dataframe()
    production = events[(events["State Type"] == "Production") & (events["Resource"] == "A")]
    return sim.product_factory.finished_products[0].info.event_time, set(production["State"])


def test_resource_executes_its_variant_of_a_process_model() -> None:
    base_end, base_steps = _run(_line({}))
    fast_end, fast_steps = _run(_line({"A": "pm_a_fast"}))
    assert "a_auto" in base_steps and "a_auto_fast" not in base_steps
    assert "a_auto_fast" in fast_steps and "a_auto" not in fast_steps
    assert fast_end == pytest.approx(base_end - 15.0, abs=0.5)


def test_variant_must_be_offered_by_the_resource() -> None:
    ps = _line({"A": "pm_unknown"})
    with pytest.raises(ValueError, match="not offered"):
        _run(ps)


def test_resource_variants_default_and_hash() -> None:
    plain = ProcessModelData(ID="pm", description="", type="ProcessModels", adjacency_matrix={"p": []})
    varied = plain.model_copy(update={"resource_variants": {"R": "pm_r"}})
    assert plain.resource_variants == {}
    assert plain.hash(None) != varied.hash(None)
