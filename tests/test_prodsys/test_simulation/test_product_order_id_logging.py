"""Order ID propagation to finished-product event log rows."""

from __future__ import annotations

from prodsys.simulation.product_info import ProductInfo, extract_order_id_from_product_id
from prodsys.simulation.state import StateEnum, StateTypeEnum


class _Sink:
    class data:
        ID = "Sink_test"


class _Product:
    class data:
        ID = "Product_J8_VFS_WR024_9"


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
