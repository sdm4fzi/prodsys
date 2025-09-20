#!/usr/bin/env python3
"""
Tests for ProcessModel and SystemResource features.

This module contains tests for the new ProcessModel and SystemResource functionality.
"""

import pytest
import prodsys.express as psx
from prodsys.models import production_system_data


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
        system_ports=["sp1", "sp2"],
        internal_routing_matrix={"sp1": ["r1"], "r1": ["r2"], "r2": ["sp2"]},
        ID="sr1"
    )
    
    data_model = system_resource.to_model()
    assert data_model.ID == "sr1"
    assert data_model.subresource_ids == ["r1", "r2"]
    assert data_model.system_ports == ["sp1", "sp2"]
    assert data_model.internal_routing_matrix == {"sp1": ["r1"], "r1": ["r2"], "r2": ["sp2"]}


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
    assert data_model.system_ports is None
    assert data_model.internal_routing_matrix is None


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


# TODO: run also simulations!