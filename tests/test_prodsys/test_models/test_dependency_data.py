"""Unit tests for the dependency data classes — focused on the new
:class:`LinkLotDependencyData` per-link override semantics.

These cases are intentionally tiny: they just lock in the
``get_link_lot_sizes`` lookup and the ``LotHandler`` resolution path so
future refactors don't silently regress the SICK xFx tray-bundling
behaviour.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from prodsys.models.dependency_data import (
    DependencyType,
    LinkLotDependencyData,
    LinkLotEntry,
    LotDependencyData,
)
from prodsys.simulation import request as request_module
from prodsys.simulation.dependency import Dependency
from prodsys.simulation.lot_handler import LotHandler


def _make_link_lot_dep() -> LinkLotDependencyData:
    """Tray (1, 34) on inter-station, single (1, 1) on intra-station."""
    return LinkLotDependencyData(
        ID="dep_lot_test",
        description="test",
        dependency_type=DependencyType.LOT,
        min_lot_size=1,
        max_lot_size=1,
        input_output="input_output",
        link_lot_sizes=[
            LinkLotEntry(origin="StationA", target="StationB",
                         min_lot_size=1, max_lot_size=34),
            LinkLotEntry(origin="StationA", target="StationA",
                         min_lot_size=1, max_lot_size=1),
        ],
    )


def test_link_lot_dependency_returns_per_link_sizes() -> None:
    dep = _make_link_lot_dep()

    assert dep.get_link_lot_sizes("StationA", "StationB") == (1, 34)
    assert dep.get_link_lot_sizes("StationA", "StationA") == (1, 1)
    assert dep.get_link_lot_sizes("Other", "Unknown") == (
        dep.min_lot_size,
        dep.max_lot_size,
    )


def test_link_lot_dependency_inherits_from_lot() -> None:
    """Pydantic + lot-handler key off ``DependencyType.LOT``."""
    dep = _make_link_lot_dep()
    assert dep.dependency_type == DependencyType.LOT
    assert isinstance(dep, LotDependencyData)


def _request_with_link(origin_id: str, target_id: str, dep: LinkLotDependencyData) -> request_module.Request:
    """Build a minimal transport request with one link-lot dependency."""
    origin = MagicMock()
    origin.data.ID = origin_id
    target = MagicMock()
    target.data.ID = target_id

    req = MagicMock(spec=request_module.Request)
    req.request_type = request_module.RequestType.TRANSPORT
    req.origin = origin
    req.target = target

    sim_dep = MagicMock(spec=Dependency)
    sim_dep.data = dep
    req.required_dependencies = [sim_dep]
    return req


def test_lot_handler_resolves_link_specific_sizes_for_transport() -> None:
    handler = LotHandler()
    dep = _make_link_lot_dep()

    inter_req = _request_with_link("StationA", "StationB", dep)
    inter = handler._get_lot_dependency_data(inter_req)
    assert inter is not None
    assert (inter.min_lot_size, inter.max_lot_size) == (1, 34)

    intra_req = _request_with_link("StationA", "StationA", dep)
    intra = handler._get_lot_dependency_data(intra_req)
    assert intra is not None
    assert (intra.min_lot_size, intra.max_lot_size) == (1, 1)


def test_lot_handler_falls_back_to_base_for_unknown_link() -> None:
    handler = LotHandler()
    dep = LinkLotDependencyData(
        ID="dep_lot_fallback",
        description="fallback test",
        dependency_type=DependencyType.LOT,
        min_lot_size=2,
        max_lot_size=7,
        input_output="input_output",
        link_lot_sizes=[
            LinkLotEntry(origin="A", target="B", min_lot_size=1, max_lot_size=99),
        ],
    )

    req = _request_with_link("X", "Y", dep)
    resolved = handler._get_lot_dependency_data(req)
    assert resolved is not None
    assert (resolved.min_lot_size, resolved.max_lot_size) == (2, 7)


def test_lot_handler_passes_through_plain_lot_dependency() -> None:
    """Non-link lot deps should round-trip unchanged."""
    handler = LotHandler()
    plain = LotDependencyData(
        ID="dep_plain",
        description="plain",
        dependency_type=DependencyType.LOT,
        min_lot_size=3,
        max_lot_size=8,
        input_output="input_output",
    )

    origin = MagicMock(); origin.data.ID = "src"
    target = MagicMock(); target.data.ID = "dst"
    req = MagicMock(spec=request_module.Request)
    req.request_type = request_module.RequestType.TRANSPORT
    req.origin = origin
    req.target = target
    sim_dep = MagicMock(spec=Dependency)
    sim_dep.data = plain
    req.required_dependencies = [sim_dep]

    resolved = handler._get_lot_dependency_data(req)
    assert resolved is plain
    assert (resolved.min_lot_size, resolved.max_lot_size) == (3, 8)
