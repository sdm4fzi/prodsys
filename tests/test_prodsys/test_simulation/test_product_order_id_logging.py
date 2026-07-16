"""Order ID propagation to finished-product event log rows."""

from __future__ import annotations

from prodsys.simulation.dependency import DependencyInfo
from prodsys.simulation.entities.entity import EntityType
from prodsys.simulation.logger import post_monitor_resource_dependency
from prodsys.simulation.product_info import ProductInfo, extract_order_id_from_product_id
from prodsys.simulation.schedule_dependency import (
    resolve_dependent_order_id,
    resolve_dependent_product_id,
)
from prodsys.simulation.state import StateEnum, StateTypeEnum


class _Sink:
    class data:
        ID = "Sink_test"


class _Product:
    class data:
        ID = "Product_J8_VFS_WR024_9"


class _DependentProduct:
    type = EntityType.PRODUCT

    class data:
        ID = "product1_3"

    class info:
        order_ID = "order_1"


def test_extract_order_id_from_product_id() -> None:
    assert extract_order_id_from_product_id("Product_J8_VFS_WR024_9") == "WR024"


def test_log_finish_product_sets_order_id_from_product_when_missing() -> None:
    info = ProductInfo()
    info.log_finish_product(_Sink(), _Product(), event_time=42.0)
    assert info.order_ID == "WR024"
    assert info.activity == StateEnum.finished_product
    assert info.state_type == StateTypeEnum.sink


def test_log_finish_product_preserves_explicit_order_id() -> None:
    info = ProductInfo(order_ID="WR099")
    info.log_finish_product(_Sink(), _Product(), event_time=1.0, order_ID="WR024")
    assert info.order_ID == "WR024"


def test_resolve_dependency_product_and_order_ids() -> None:
    product = _DependentProduct()

    assert resolve_dependent_product_id(product) == "product1_3"
    assert resolve_dependent_order_id(product) == "order_1"


def test_resource_dependency_event_contains_product_and_order_ids() -> None:
    info = DependencyInfo(resource_id="worker2")
    events: list[dict] = []

    info.log_start_dependency(
        event_time=1.5,
        requesting_item_id="machine2",
        dependency_id="resource_2_dependency",
        product_id="product1_3",
        order_id="order_1",
    )
    post_monitor_resource_dependency(events, info)

    assert events == [
        {
            "Time": 1.5,
            "Resource": "worker2",
            "State": "Dependency",
            "State Type": StateTypeEnum.dependency,
            "Activity": StateEnum.start_state,
            "Product": "product1_3",
            "Expected End Time": None,
            "Origin location": None,
            "Target location": None,
            "Empty Transport": None,
            "Requesting Item": "machine2",
            "Dependency": "resource_2_dependency",
            "process": None,
            "Order ID": "order_1",
        }
    ]
