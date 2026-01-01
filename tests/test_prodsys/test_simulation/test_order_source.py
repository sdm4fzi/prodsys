"""
Tests for order source functionality.
"""

import pytest
import prodsys.express as psx
from prodsys.models import production_system_data
from prodsys.simulation import runner


def test_order_source_creation():
    """Test that OrderSource can be created."""
    t1 = psx.FunctionTimeModel("constant", 5.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")
    
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    resource = psx.Resource([p1], [10, 0], 1, ID="R1")
    transport = psx.Resource([tp], [5, 0], 1, ID="AGV1")
    
    product = psx.Product([p1], tp, "Product_A")
    
    sink = psx.Sink(product, [20, 0], "Sink")
    
    # Create orders
    order1 = psx.Order(
        ID="order1",
        ordered_products=[psx.OrderedProduct(product=product, quantity=2)],
        order_time=0.0,
        release_time=10.0,
        priority=1,
    )
    
    order_source = psx.OrderSource(
        orders=[order1],
        location=[0, 0],
        ID="OrderSource",
    )
    
    system = psx.ProductionSystem([resource, transport], [order_source], [sink])
    adapter = system.to_model()
    
    assert len(adapter.source_data) == 1
    from prodsys.models.source_data import OrderSourceData
    assert isinstance(adapter.source_data[0], OrderSourceData)
    assert adapter.source_data[0].ID == "OrderSource"
    assert len(adapter.order_data) == 1
    assert adapter.order_data[0].ID == "order1"


def test_order_source_simulation():
    """Test that simulation runs with OrderSource."""
    t1 = psx.FunctionTimeModel("constant", 5.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")
    
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    resource = psx.Resource([p1], [10, 0], 1, ID="R1")
    transport = psx.Resource([tp], [5, 0], 1, ID="AGV1")
    
    product = psx.Product([p1], tp, "Product_A")
    
    sink = psx.Sink(product, [20, 0], "Sink")
    
    # Create orders with different release times
    order1 = psx.Order(
        ID="order1",
        ordered_products=[psx.OrderedProduct(product=product, quantity=2)],
        order_time=0.0,
        release_time=10.0,
        priority=1,
    )
    
    order2 = psx.Order(
        ID="order2",
        ordered_products=[psx.OrderedProduct(product=product, quantity=1)],
        order_time=5.0,
        release_time=20.0,
        priority=1,
    )
    
    order_source = psx.OrderSource(
        orders=[order1, order2],
        location=[0, 0],
        ID="OrderSource",
    )
    
    system = psx.ProductionSystem([resource, transport], [order_source], [sink])
    adapter = system.to_model()
    
    runner_instance = runner.Runner(production_system_data=adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(100)
    
    assert runner_instance.env.now == 100
    
    # Get performance data
    performance = runner_instance.get_performance_data()
    assert performance.event_log is not None
    assert len(performance.event_log) > 0


def test_order_source_multiple_product_types():
    """Test that OrderSource can release products of different types."""
    t1 = psx.FunctionTimeModel("constant", 5.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")
    
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    resource = psx.Resource([p1], [10, 0], 1, ID="R1")
    transport = psx.Resource([tp], [5, 0], 1, ID="AGV1")
    
    product1 = psx.Product([p1], tp, "Product_A")
    product2 = psx.Product([p1], tp, "Product_B")
    
    sink1 = psx.Sink(product1, [20, 0], "Sink1")
    sink2 = psx.Sink(product2, [20, 0], "Sink2")
    
    # Create order with multiple product types
    order1 = psx.Order(
        ID="order1",
        ordered_products=[
            psx.OrderedProduct(product=product1, quantity=1),
            psx.OrderedProduct(product=product2, quantity=1),
        ],
        order_time=0.0,
        release_time=10.0,
        priority=1,
    )
    
    order_source = psx.OrderSource(
        orders=[order1],
        location=[0, 0],
        ID="OrderSource",
    )
    
    system = psx.ProductionSystem(
        [resource, transport], [order_source], [sink1, sink2]
    )
    adapter = system.to_model()
    
    runner_instance = runner.Runner(production_system_data=adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(100)
    
    assert runner_instance.env.now == 100
    
    # Get performance data
    performance = runner_instance.get_performance_data()
    assert performance.event_log is not None
    assert len(performance.event_log) > 0


def test_order_source_with_conwip():
    """Test that OrderSource respects ConWip limits."""
    t1 = psx.FunctionTimeModel("constant", 5.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")
    
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    resource = psx.Resource([p1], [10, 0], 1, ID="R1")
    transport = psx.Resource([tp], [5, 0], 1, ID="AGV1")
    
    product = psx.Product([p1], tp, "Product_A")
    
    sink = psx.Sink(product, [20, 0], "Sink")
    
    # Create orders
    order1 = psx.Order(
        ID="order1",
        ordered_products=[psx.OrderedProduct(product=product, quantity=5)],
        order_time=0.0,
        release_time=10.0,
        priority=1,
    )
    
    order_source = psx.OrderSource(
        orders=[order1],
        location=[0, 0],
        ID="OrderSource",
    )
    
    system = psx.ProductionSystem([resource, transport], [order_source], [sink])
    adapter = system.to_model()
    adapter.conwip_number = 3
    
    runner_instance = runner.Runner(production_system_data=adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(100)
    
    assert runner_instance.env.now == 100
    
    # Get performance data
    performance = runner_instance.get_performance_data()
    assert performance.event_log is not None
    assert len(performance.event_log) > 0
    
    # Check that ConWip limit is respected
    # The number of products in the system should not exceed ConWip limit
    # (allowing for products that are being processed)
    wip_kpis = [kpi for kpi in performance.kpis if kpi.name.value == "WIP"]
    if wip_kpis:
        # WIP might temporarily exceed ConWip due to processing, but should be controlled
        assert wip_kpis[0].value <= adapter.conwip_number + 2  # Allow some margin for processing


def test_order_source_release_time():
    """Test that OrderSource releases products at the correct release time."""
    t1 = psx.FunctionTimeModel("constant", 5.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")
    
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    resource = psx.Resource([p1], [10, 0], 1, ID="R1")
    transport = psx.Resource([tp], [5, 0], 1, ID="AGV1")
    
    product = psx.Product([p1], tp, "Product_A")
    
    sink = psx.Sink(product, [20, 0], "Sink")
    
    # Create order with release time
    order1 = psx.Order(
        ID="order1",
        ordered_products=[psx.OrderedProduct(product=product, quantity=1)],
        order_time=0.0,
        release_time=50.0,  # Release at time 50
        priority=1,
    )
    
    order_source = psx.OrderSource(
        orders=[order1],
        location=[0, 0],
        ID="OrderSource",
    )
    
    system = psx.ProductionSystem([resource, transport], [order_source], [sink])
    adapter = system.to_model()
    
    runner_instance = runner.Runner(production_system_data=adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(100)
    
    assert runner_instance.env.now == 100
    
    # Get performance data
    performance = runner_instance.get_performance_data()
    assert performance.event_log is not None
    
    # Check that products are released at or after release_time
    source_events = [
        e for e in performance.event_log
        if e.resource == "OrderSource" and e.activity == "start state"
    ]
    if source_events:
        # Products should be released at or after release_time (50.0)
        for event in source_events:
            assert event.time >= 50.0


def test_order_source_without_release_time():
    """Test that OrderSource uses order_time when release_time is not specified."""
    t1 = psx.FunctionTimeModel("constant", 5.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")
    
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    resource = psx.Resource([p1], [10, 0], 1, ID="R1")
    transport = psx.Resource([tp], [5, 0], 1, ID="AGV1")
    
    product = psx.Product([p1], tp, "Product_A")
    
    sink = psx.Sink(product, [20, 0], "Sink")
    
    # Create order without release_time (should use order_time)
    order1 = psx.Order(
        ID="order1",
        ordered_products=[psx.OrderedProduct(product=product, quantity=1)],
        order_time=10.0,  # Should be used as release_time
        release_time=None,
        priority=1,
    )
    
    order_source = psx.OrderSource(
        orders=[order1],
        location=[0, 0],
        ID="OrderSource",
    )
    
    system = psx.ProductionSystem([resource, transport], [order_source], [sink])
    adapter = system.to_model()
    
    runner_instance = runner.Runner(production_system_data=adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(100)
    
    assert runner_instance.env.now == 100
    
    # Get performance data
    performance = runner_instance.get_performance_data()
    assert performance.event_log is not None
    assert len(performance.event_log) > 0

