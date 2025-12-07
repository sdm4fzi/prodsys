#!/usr/bin/env python3
"""
Tests for ProcessModel and SystemResource features.

This module contains tests for the new ProcessModel and SystemResource functionality.
"""

import prodsys.express as psx


def test_process_models_creation():
    """Test that process models can be created and converted to data models."""
    # Test ProcessModel
    tm = psx.FunctionTimeModel("normal", 1.0, 0.1, "tm1")
    process_model = psx.ProcessModel(
        time_model=tm,
        process_ids=["p1", "p2"],
        adjacency_matrix={"p1": ["p2"], "p2": []},
        ID="pm1"
    )
    data_model = process_model.to_model()
    assert data_model.ID == "pm1"
    assert data_model.process_ids == ["p1", "p2"]
    assert data_model.adjacency_matrix == {"p1": ["p2"], "p2": []}

    # Test SequentialProcess
    sequential_process = psx.SequentialProcess(
        time_model=tm,
        process_ids=["p1", "p2", "p3"],
        ID="sp1"
    )
    seq_data_model = sequential_process.to_model()
    assert seq_data_model.ID == "sp1"
    assert seq_data_model.process_ids == ["p1", "p2", "p3"]
    expected_adjacency = {"p1": ["p2"], "p2": ["p3"], "p3": []}
    assert seq_data_model.adjacency_matrix == expected_adjacency

    # Test LoadingProcess
    loading_process = psx.LoadingProcess(
        time_model=tm,
        dependency_type="before",
        can_be_chained=True,
        ID="lp1"
    )
    lp_data_model = loading_process.to_model()
    assert lp_data_model.ID == "lp1"
    assert lp_data_model.dependency_type == "before"
    assert lp_data_model.can_be_chained is True


def test_system_resource_creation():
    """Test that system resources can be created and converted to data models."""
    tm = psx.FunctionTimeModel("normal", 1.0, 0.1, "tm1")
    p1 = psx.ProductionProcess(tm, "p1")
    
    system_resource = psx.SystemResource(
        processes=[p1],
        location=[10, 10],
        subresource_ids=["r1", "r2"],
        ID="sr1"
    )
    
    data_model = system_resource.to_model()
    assert data_model.ID == "sr1"
    assert data_model.subresource_ids == ["r1", "r2"]

def test_product_with_process_model():
    """Test that products can use process models."""
    tm = psx.FunctionTimeModel("normal", 1.0, 0.1, "tm1")
    tp_tm = psx.DistanceTimeModel(60, 0.1, "manhattan", "tp_tm")

    process_model = psx.ProcessModel(
        time_model=tm,
        process_ids=["p1", "p2"],
        adjacency_matrix={"p1": ["p2"], "p2": []},
        ID="pm1"
    )
    
    transport_process = psx.TransportProcess(tp_tm, "tp1")
    
    product = psx.Product(
        process=process_model,
        transport_process=transport_process,
        ID="product1"
    )
    
    data_model = product.to_model()
    assert data_model.ID == "product1"
    assert len(data_model.processes) == 2  # adjacency matrix has 2 processes: p1 and p2
    assert "p1" in data_model.processes
    assert "p2" in data_model.processes


def test_sequential_process_auto_adjacency():
    """Test that SequentialProcess automatically generates adjacency matrix."""
    tm = psx.FunctionTimeModel("normal", 1.0, 0.1, "tm1")
    
    # Test with 3 processes
    seq_process = psx.SequentialProcess(
        time_model=tm,
        process_ids=["p1", "p2", "p3"],
        ID="seq1"
    )
    
    expected_adjacency = {"p1": ["p2"], "p2": ["p3"], "p3": []}
    assert seq_process.adjacency_matrix == expected_adjacency
    
    # Test with 2 processes
    seq_process2 = psx.SequentialProcess(
        time_model=tm,
        process_ids=["p1", "p2"],
        ID="seq2"
    )
    
    expected_adjacency2 = {"p1": ["p2"], "p2": []}
    assert seq_process2.adjacency_matrix == expected_adjacency2


def test_loading_process_dependency_types():
    """Test that LoadingProcess supports different dependency types."""
    tm = psx.FunctionTimeModel("normal", 1.0, 0.1, "tm1")
    
    # Test "before" dependency
    lp_before = psx.LoadingProcess(
        time_model=tm,
        dependency_type="before",
        can_be_chained=True,
        ID="lp_before"
    )
    assert lp_before.dependency_type == "before"
    
    # Test "after" dependency
    lp_after = psx.LoadingProcess(
        time_model=tm,
        dependency_type="after",
        can_be_chained=False,
        ID="lp_after"
    )
    assert lp_after.dependency_type == "after"
    assert lp_after.can_be_chained is False
    
    # Test "parallel" dependency
    lp_parallel = psx.LoadingProcess(
        time_model=tm,
        dependency_type="parallel",
        can_be_chained=True,
        ID="lp_parallel"
    )
    assert lp_parallel.dependency_type == "parallel"


def test_process_model_can_contain_other_models():
    """Test that ProcessModel can be configured to contain other models."""
    tm = psx.FunctionTimeModel("normal", 1.0, 0.1, "tm1")
    
    # Test with can_contain_other_models=True
    pm_with_models = psx.ProcessModel(
        time_model=tm,
        process_ids=["p1", "p2"],
        adjacency_matrix={"p1": ["p2"], "p2": []},
        can_contain_other_models=True,
        ID="pm_with_models"
    )
    assert pm_with_models.can_contain_other_models is True
    
    # Test with can_contain_other_models=False (default)
    pm_without_models = psx.ProcessModel(
        time_model=tm,
        process_ids=["p1", "p2"],
        adjacency_matrix={"p1": ["p2"], "p2": []},
        ID="pm_without_models"
    )
    assert pm_without_models.can_contain_other_models is False


def test_system_resource_without_ports():
    """Test that SystemResource can be created without system ports."""
    tm = psx.FunctionTimeModel("normal", 1.0, 0.1, "tm1")
    p1 = psx.ProductionProcess(tm, "p1")
    
    system_resource = psx.SystemResource(
        processes=[p1],
        location=[10, 10],
        subresource_ids=["r1", "r2"],
        ID="sr1"
    )
    
    data_model = system_resource.to_model()
    assert data_model.ID == "sr1"
    assert data_model.subresource_ids == ["r1", "r2"]


def test_data_model_conversion():
    """Test that all new models can be converted to data models correctly."""
    tm = psx.FunctionTimeModel("normal", 1.0, 0.1, "tm1")
    
    # Test ProcessModel conversion
    pm = psx.ProcessModel(
        time_model=tm,
        process_ids=["p1", "p2"],
        adjacency_matrix={"p1": ["p2"], "p2": []},
        ID="pm1"
    )
    pm_data = pm.to_model()
    assert pm_data.type.value == "ProcessModels"
    
    # Test SequentialProcess conversion
    sp = psx.SequentialProcess(
        time_model=tm,
        process_ids=["p1", "p2"],
        ID="sp1"
    )
    sp_data = sp.to_model()
    assert sp_data.type.value == "ProcessModels"
    
    # Test LoadingProcess conversion
    lp = psx.LoadingProcess(
        time_model=tm,
        dependency_type="before",
        can_be_chained=True,
        ID="lp1"
    )
    lp_data = lp.to_model()
    assert lp_data.type.value == "LoadingProcesses"
    
    # Test SystemResource conversion
    sr = psx.SystemResource(
        processes=[pm],
        location=[10, 10],
        subresource_ids=["r1"],
        ID="sr1"
    )
    sr_data = sr.to_model()
    assert sr_data.ID == "sr1"
    assert sr_data.subresource_ids == ["r1"]


def test_system_resource_with_robot_simulation():
    """Test a complete simulation with SystemResource containing robot and machines."""
    
    # ========== TIME MODELS ==========
    tm_machine1 = psx.FunctionTimeModel(
        distribution_function="normal",
        location=1.8,
        scale=0.2,
        ID="tm_machine1"
    )
    tm_machine2 = psx.FunctionTimeModel(
        distribution_function="normal",
        location=2.2,
        scale=0.7,
        ID="tm_machine2"
    )
    tm_machine3 = psx.FunctionTimeModel(
        distribution_function="normal",
        location=2.0,
        scale=0.5,
        ID="tm_machine3"
    )
    
    tm_agv = psx.DistanceTimeModel(
        speed=60.0,
        reaction_time=0.1,
        metric="manhattan",
        ID="tm_agv"
    )
    tm_arrival = psx.FunctionTimeModel(
        distribution_function="exponential",
        location=2.5,
        ID="tm_arrival"
    )
    
    # ========== PROCESSES ==========
    machine1_process = psx.ProductionProcess(
        time_model=tm_machine1,
        ID="machine1_process"
    )
    machine2_process = psx.ProductionProcess(
        time_model=tm_machine2,
        ID="machine2_process"
    )
    machine3_process = psx.ProductionProcess(
        time_model=tm_machine3,
        ID="machine3_process"
    )
    
    agv_transport = psx.TransportProcess(
        time_model=tm_agv,
        ID="agv_transport"
    )
    
    # ========== PROCESS MODEL ==========
    cell_process_model = psx.ProcessModel(
        adjacency_matrix={
            "machine1_process": ["machine2_process"],
            "machine2_process": []
        },
        ID="cell_process_model"
    )
    
    product_process_model = psx.ProcessModel(
        can_contain_other_models=True,
        ID="product_process_model",
        adjacency_matrix={
            "machine3_process": ["cell_process_model"],
            "cell_process_model": []
        }
    )
    
    # ========== RESOURCES ==========
    robot = psx.Resource(
        processes=[agv_transport],
        location=[12, 10],
        capacity=1,
        ID="robot"
    )
    
    machine1 = psx.Resource(
        processes=[machine1_process],
        location=[12, 8],
        capacity=1,
        ID="machine1"
    )
    machine2 = psx.Resource(
        processes=[machine2_process],
        location=[12, 12],
        capacity=1,
        ID="machine2"
    )
    machine3 = psx.Resource(
        processes=[machine3_process],
        location=[12, 16],
        capacity=1,
        ID="machine3"
    )
    
    agv = psx.Resource(
        processes=[agv_transport],
        location=[0, 10],
        capacity=1,
        ID="agv"
    )
    
    # ========== SYSTEM RESOURCE (CELL) ==========
    manufacturing_cell = psx.SystemResource(
        processes=[cell_process_model],
        location=[10, 10],
        subresource_ids=["robot", "machine1", "machine2"],
        capacity=5,
        ID="manufacturing_cell"
    )
    
    # ========== PRODUCT ==========
    product = psx.Product(
        process=product_process_model,
        transport_process=agv_transport,
        ID="product"
    )
    
    # ========== SOURCES AND SINKS ==========
    source = psx.Source(product, tm_arrival, [0, 10], ID="source")
    sink = psx.Sink(product, [20, 10], ID="sink")
    
    # ========== PRODUCTION SYSTEM ==========
    system = psx.ProductionSystem(
        resources=[robot, machine1, machine2, machine3, manufacturing_cell, agv],
        sources=[source],
        sinks=[sink],
        ID="production_system"
    )
    
    # ========== VALIDATION AND SIMULATION ==========
    system.validate()
    system_data = system.to_model()
    
    # Validate system structure
    assert len(system_data.resource_data) == 6
    assert "manufacturing_cell" in [r.ID for r in system_data.resource_data]
    
    # Run simulation^
    system.run(time_range=1000)
    system.runner.print_results()
    
    # Get post processor for KPI validation
    post_processor = system.runner.get_post_processor()
    
    # Validate output and throughput KPIs (from terminal: Output=395, Throughput=0.397259)
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output" and kpi.product_type == "product":
            assert kpi.value > 350 and kpi.value < 420, f"Output {kpi.value} out of expected range"
    # Validate WIP KPIs (from terminal: WIP=10.180611)
    for kpi in post_processor.WIP_KPIs:
        if kpi.name == "WIP" and kpi.product_type == "product":
            assert kpi.value > 15.0 and kpi.value < 20.0, f"WIP {kpi.value} out of expected range"
    
    # Validate throughput time (from terminal: 22.857539)
    for kpi in post_processor.aggregated_throughput_time_KPIs:
        if kpi.name == "throughput_time":
            assert kpi.value > 35.0 and kpi.value < 45.0, f"Throughput time {kpi.value} out of expected range"
    
    # Validate resource states (from terminal output)
    for kpi in post_processor.machine_state_KPIS:
        if kpi.name == "productive_time":
            if kpi.resource == "machine1":
                # Expected: ~71.7%
                assert kpi.value > 65 and kpi.value < 78, f"Machine1 productive time {kpi.value} out of expected range"
            elif kpi.resource == "machine2":
                # Expected: ~86.6%
                assert kpi.value > 80 and kpi.value < 92, f"Machine2 productive time {kpi.value} out of expected range"
            elif kpi.resource == "machine3":
                # Expected: ~80.3%
                assert kpi.value > 75 and kpi.value < 86, f"Machine3 productive time {kpi.value} out of expected range"
            elif kpi.resource == "agv":
                # Expected: ~64.3%
                assert kpi.value > 58 and kpi.value < 70, f"AGV productive time {kpi.value} out of expected range"
            elif kpi.resource == "robot":
                # Expected: ~27.6%
                assert kpi.value > 32 and kpi.value < 38, f"Robot productive time {kpi.value} out of expected range"