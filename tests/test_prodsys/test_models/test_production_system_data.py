"""
Tests for production_system_data module validation.
"""

import pytest
from pydantic import ValidationError
from prodsys.models.production_system_data import ProductionSystemData
from prodsys.models import (
    time_model_data,
    state_data,
    processes_data,
    port_data,
    resource_data,
    product_data,
    sink_data,
    source_data,
    node_data,
)


class TestFieldValidators:
    """Tests for field validators in ProductionSystemData."""

    def test_check_states_invalid_time_model(self):
        """Test that states with invalid time models raise ValidationError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        state = state_data.BreakDownStateData(
            ID="state1",
            description="State 1",
            time_model_id="invalid_tm",  # Invalid time model ID
            type="BreakDownState",
            repair_time_model_id="tm1",
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                state_data=[state],
            )
        
        assert "time model" in str(exc_info.value).lower()
        assert "state1" in str(exc_info.value)

    def test_check_processes_invalid_time_model(self):
        """Test that processes with invalid time models raise ValidationError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="invalid_tm",  # Invalid time model ID
            type="ProductionProcesses",
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                process_data=[process],
            )
        
        assert "time model" in str(exc_info.value).lower()
        assert "P1" in str(exc_info.value)

    def test_check_resources_invalid_process(self):
        """Test that resources with invalid processes raise ValidationError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        resource = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["invalid_process"],  # Invalid process ID
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                process_data=[process],
                resource_data=[resource],
            )
        
        assert "process" in str(exc_info.value).lower()
        assert "R1" in str(exc_info.value)

    def test_check_resources_invalid_state(self):
        """Test that resources with invalid states raise ValidationError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        state = state_data.BreakDownStateData(
            ID="state1",
            description="State 1",
            time_model_id="tm1",
            type="BreakDownState",
            repair_time_model_id="tm1",
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        resource = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
            state_ids=["invalid_state"],  # Invalid state ID
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                state_data=[state],
                process_data=[process],
                resource_data=[resource],
            )
        
        assert "state" in str(exc_info.value).lower()
        assert "R1" in str(exc_info.value)

    def test_check_resources_invalid_port(self):
        """Test that resources with invalid ports raise ValidationError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        queue = port_data.QueueData(
            ID="Q1",
            description="Queue 1",
            capacity=10,
            location=[10.0, 10.0],
            interface_type=port_data.PortInterfaceType.INPUT,
        )
        
        resource = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
            ports=["invalid_port"],  # Invalid port ID
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                process_data=[process],
                port_data=[queue],
                resource_data=[resource],
            )
        
        assert "port" in str(exc_info.value).lower()
        assert "R1" in str(exc_info.value)

    def test_check_resources_missing_output_port(self):
        """Test that resources without output ports raise ValidationError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        # Only input queue, no output queue
        queue = port_data.QueueData(
            ID="Q1",
            description="Queue 1",
            capacity=10,
            location=[10.0, 10.0],
            interface_type=port_data.PortInterfaceType.INPUT,
        )
        
        resource = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
            ports=["Q1"],
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                process_data=[process],
                port_data=[queue],
                resource_data=[resource],
            )
        
        assert "output port" in str(exc_info.value).lower()
        assert "R1" in str(exc_info.value)

    def test_check_resources_missing_input_port(self):
        """Test that resources without input ports raise ValidationError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        # Only output queue, no input queue
        queue = port_data.QueueData(
            ID="Q1",
            description="Queue 1",
            capacity=10,
            location=[10.0, 10.0],
            interface_type=port_data.PortInterfaceType.OUTPUT,
        )
        
        resource = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
            ports=["Q1"],
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                process_data=[process],
                port_data=[queue],
                resource_data=[resource],
            )
        
        assert "input port" in str(exc_info.value).lower()
        assert "R1" in str(exc_info.value)

    def test_check_products_invalid_transport_process(self):
        """Test that products with invalid transport processes raise ValidationError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        product = product_data.ProductData(
            ID="Product1",
            description="Product 1",
            type="Product1",
            processes={"P1": []},
            transport_process="invalid_transport",  # Invalid transport process
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                process_data=[process],
                product_data=[product],
            )
        
        assert "transport process" in str(exc_info.value).lower()
        assert "Product1" in str(exc_info.value)

    def test_check_products_invalid_required_process(self):
        """Test that products with invalid required processes raise ValidationError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        transport = processes_data.TransportProcessData(
            ID="TP1",
            description="Transport 1",
            time_model_id="tm1",
            type="TransportProcesses",
        )
        
        product = product_data.ProductData(
            ID="Product1",
            description="Product 1",
            type="Product1",
            processes={"P1": [], "invalid_process": []},  # Invalid process
            transport_process="TP1",
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                process_data=[process, transport],
                product_data=[product],
            )
        
        assert "processes" in str(exc_info.value).lower()
        assert "Product1" in str(exc_info.value)

    def test_check_sinks_invalid_product_type(self):
        """Test that sinks with invalid product types raise ValidationError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        transport = processes_data.TransportProcessData(
            ID="TP1",
            description="Transport 1",
            time_model_id="tm1",
            type="TransportProcesses",
        )
        
        product = product_data.ProductData(
            ID="Product1",
            description="Product 1",
            type="Product1",
            processes={"P1": []},
            transport_process="TP1",
        )
        
        sink = sink_data.SinkData(
            ID="Sink1",
            description="Sink 1",
            location=[50.0, 50.0],
            product_type="invalid_product",  # Invalid product type
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                process_data=[transport],
                product_data=[product],
                sink_data=[sink],
            )
        
        assert "product" in str(exc_info.value).lower()
        # Cross-field validation runs in fixed order; may raise on sink (Sink1) or product (processes) first
        msg = str(exc_info.value)
        assert (
            "Sink1" in msg
            or "missing or faulty" in msg.lower()
            or "processes" in msg.lower()
            or "Product1" in msg
        )

    def test_check_sinks_missing_input_port(self):
        """Test that sinks without input ports raise ValidationError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        transport = processes_data.TransportProcessData(
            ID="TP1",
            description="Transport 1",
            time_model_id="tm1",
            type="TransportProcesses",
        )
        
        product = product_data.ProductData(
            ID="Product1",
            description="Product 1",
            type="Product1",
            processes={},
            transport_process="TP1",
        )
        
        # Only output queue, no input queue
        queue = port_data.QueueData(
            ID="Q1",
            description="Queue 1",
            capacity=10,
            location=[50.0, 50.0],
            interface_type=port_data.PortInterfaceType.OUTPUT,
        )
        
        sink = sink_data.SinkData(
            ID="Sink1",
            description="Sink 1",
            location=[50.0, 50.0],
            product_type="Product1",
            ports=["Q1"],
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                process_data=[transport],
                product_data=[product],
                port_data=[queue],
                sink_data=[sink],
            )
        
        assert "input port" in str(exc_info.value).lower()
        assert "Sink1" in str(exc_info.value)

    def test_check_sources_invalid_time_model(self):
        """Test that sources with invalid time models raise ValidationError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        transport = processes_data.TransportProcessData(
            ID="TP1",
            description="Transport 1",
            time_model_id="tm1",
            type="TransportProcesses",
        )
        
        product = product_data.ProductData(
            ID="Product1",
            description="Product 1",
            type="Product1",
            processes={},
            transport_process="TP1",
        )
        
        source = source_data.SourceData(
            ID="Source1",
            description="Source 1",
            location=[0.0, 0.0],
            product_type="Product1",
            time_model_id="invalid_tm",  # Invalid time model
            routing_heuristic="random",
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                process_data=[transport],
                product_data=[product],
                source_data=[source],
            )
        
        assert "time model" in str(exc_info.value).lower()
        assert "Source1" in str(exc_info.value)

    def test_check_sources_invalid_product_type(self):
        """Test that sources with invalid product types raise ValidationError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        transport = processes_data.TransportProcessData(
            ID="TP1",
            description="Transport 1",
            time_model_id="tm1",
            type="TransportProcesses",
        )
        
        product = product_data.ProductData(
            ID="Product1",
            description="Product 1",
            type="Product1",
            processes={},
            transport_process="TP1",
        )
        
        source = source_data.SourceData(
            ID="Source1",
            description="Source 1",
            location=[0.0, 0.0],
            product_type="invalid_product",  # Invalid product type
            time_model_id="tm1",
            routing_heuristic="random",
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                process_data=[transport],
                product_data=[product],
                source_data=[source],
            )
        
        assert "product" in str(exc_info.value).lower()
        assert "Source1" in str(exc_info.value)

    def test_check_sources_missing_output_port(self):
        """Test that sources without output ports raise ValidationError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        transport = processes_data.TransportProcessData(
            ID="TP1",
            description="Transport 1",
            time_model_id="tm1",
            type="TransportProcesses",
        )
        
        product = product_data.ProductData(
            ID="Product1",
            description="Product 1",
            type="Product1",
            processes={},
            transport_process="TP1",
        )
        
        # Only input queue, no output queue
        queue = port_data.QueueData(
            ID="Q1",
            description="Queue 1",
            capacity=10,
            location=[0.0, 0.0],
            interface_type=port_data.PortInterfaceType.INPUT,
        )
        
        source = source_data.SourceData(
            ID="Source1",
            description="Source 1",
            location=[0.0, 0.0],
            product_type="Product1",
            time_model_id="tm1",
            routing_heuristic="random",
            ports=["Q1"],
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                process_data=[transport],
                product_data=[product],
                port_data=[queue],
                source_data=[source],
            )
        
        assert "output port" in str(exc_info.value).lower()
        assert "Source1" in str(exc_info.value)


class TestDuplicateIDValidation:
    """Tests for duplicate ID validation."""

    def test_duplicate_ids_across_different_types(self):
        """Test that duplicate IDs across different data types raise ValidationError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="shared_id",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="shared_id",  # Same ID as time model
            description="Process 1",
            time_model_id="shared_id",
            type="ProductionProcesses",
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                process_data=[process],
            )
        
        assert "duplicate ids" in str(exc_info.value).lower()
        assert "shared_id" in str(exc_info.value)

    def test_duplicate_ids_node_and_resource(self):
        """Test that duplicate IDs between nodes and resources raise ValidationError."""
        node = node_data.NodeData(
            ID="shared_id",
            description="Node 1",
            location=[10.0, 10.0],
        )
        
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        resource = resource_data.ResourceData(
            ID="shared_id",  # Same ID as node
            description="Resource 1",
            location=[20.0, 20.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                process_data=[process],
                node_data=[node],
                resource_data=[resource],
            )
        
        assert "duplicate ids" in str(exc_info.value).lower()
        assert "shared_id" in str(exc_info.value)

    def test_duplicate_ids_source_and_sink(self):
        """Test that duplicate IDs between sources and sinks raise ValidationError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        transport = processes_data.TransportProcessData(
            ID="TP1",
            description="Transport 1",
            time_model_id="tm1",
            type="TransportProcesses",
        )
        
        product = product_data.ProductData(
            ID="Product1",
            description="Product 1",
            type="Product1",
            processes={},
            transport_process="TP1",
        )
        
        source = source_data.SourceData(
            ID="shared_id",
            description="Source 1",
            location=[0.0, 0.0],
            product_type="Product1",
            time_model_id="tm1",
            routing_heuristic="random",
        )
        
        sink = sink_data.SinkData(
            ID="shared_id",  # Same ID as source
            description="Sink 1",
            location=[50.0, 50.0],
            product_type="Product1",
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                process_data=[transport],
                product_data=[product],
                source_data=[source],
                sink_data=[sink],
            )
        
        assert "duplicate ids" in str(exc_info.value).lower()
        assert "shared_id" in str(exc_info.value)

    def test_unique_ids_allowed(self):
        """Test that unique IDs across all types are allowed."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        node = node_data.NodeData(
            ID="N1",
            description="Node 1",
            location=[10.0, 10.0],
        )
        
        resource = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[20.0, 20.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
        )
        
        # Should not raise an error
        system = ProductionSystemData(
            ID="test",
            time_model_data=[tm1],
            process_data=[process],
            node_data=[node],
            resource_data=[resource],
        )
        
        assert system.ID == "test"
        assert len(system.time_model_data) == 1
        assert len(system.process_data) == 1
        assert len(system.node_data) == 1
        assert len(system.resource_data) == 1


class TestIncrementalAddition:
    """Tests for adding components incrementally without validation errors."""

    def test_add_components_one_by_one(self):
        """Test that components can be added one by one without validation errors."""
        # Start with empty system
        system = ProductionSystemData(ID="test")
        
        # Add time models
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        tm2 = time_model_data.FunctionTimeModelData(
            ID="tm2",
            description="Time model 2",
            distribution_function="constant",
            location=5.0,
            scale=0.0,
        )
        system.time_model_data.append(tm1)
        system.time_model_data.append(tm2)
        system.revalidate()  # Should not raise
        
        # Add processes
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        transport = processes_data.TransportProcessData(
            ID="TP1",
            description="Transport 1",
            time_model_id="tm2",
            type="TransportProcesses",
        )
        system.process_data.append(process)
        system.process_data.append(transport)
        system.revalidate()  # Should not raise
        
        # Add states
        state = state_data.BreakDownStateData(
            ID="state1",
            description="State 1",
            time_model_id="tm1",
            type="BreakDownState",
            repair_time_model_id="tm2",
        )
        system.state_data.append(state)
        system.revalidate()  # Should not raise
        
        # Add ports
        queue1 = port_data.QueueData(
            ID="Q1",
            description="Queue 1",
            capacity=10,
            location=[10.0, 10.0],
            interface_type=port_data.PortInterfaceType.INPUT,
        )
        queue2 = port_data.QueueData(
            ID="Q2",
            description="Queue 2",
            capacity=10,
            location=[10.0, 10.0],
            interface_type=port_data.PortInterfaceType.OUTPUT,
        )
        system.port_data.append(queue1)
        system.port_data.append(queue2)
        system.revalidate()  # Should not raise
        
        # Add resources
        resource = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
            state_ids=["state1"],
            ports=["Q1", "Q2"],
        )
        system.resource_data.append(resource)
        system.revalidate()  # Should not raise
        
        # Add products
        product = product_data.ProductData(
            ID="Product1",
            description="Product 1",
            type="Product1",
            processes={"P1": []},
            transport_process="TP1",
        )
        system.product_data.append(product)
        system.revalidate()  # Should not raise
        
        # Add sources
        source = source_data.SourceData(
            ID="Source1",
            description="Source 1",
            location=[0.0, 0.0],
            product_type="Product1",
            time_model_id="tm1",
            routing_heuristic="random",
        )
        system.source_data.append(source)
        system.revalidate()  # Should not raise
        
        # Add sinks
        sink = sink_data.SinkData(
            ID="Sink1",
            description="Sink 1",
            location=[50.0, 50.0],
            product_type="Product1",
        )
        system.sink_data.append(sink)
        system.revalidate()  # Should not raise
        
        # Final validation
        assert len(system.time_model_data) == 2
        assert len(system.process_data) == 2
        assert len(system.state_data) == 1
        assert len(system.port_data) == 4
        assert len(system.resource_data) == 1
        assert len(system.product_data) == 1
        assert len(system.source_data) == 1
        assert len(system.sink_data) == 1

    def test_add_duplicate_id_after_initial_creation(self):
        """Test that adding duplicate IDs after initial creation is caught by revalidate."""
        system = ProductionSystemData(
            ID="test",
            time_model_data=[
                time_model_data.FunctionTimeModelData(
                    ID="tm1",
                    description="Time model 1",
                    distribution_function="constant",
                    location=10.0,
                    scale=0.0,
                )
            ],
        )
        
        # Add a process with duplicate ID
        duplicate_process = processes_data.ProductionProcessData(
            ID="tm1",  # Duplicate of time model ID
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        system.process_data.append(duplicate_process)
        
        with pytest.raises(ValidationError) as exc_info:
            system.revalidate()
        
        assert "duplicate ids" in str(exc_info.value).lower()
        assert "tm1" in str(exc_info.value)


class TestSystemTransformations:
    """Tests for system transformations like adding/removing machines."""

    @pytest.fixture
    def base_system(self):
        """Create a base valid system for transformation tests."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        transport = processes_data.TransportProcessData(
            ID="TP1",
            description="Transport 1",
            time_model_id="tm1",
            type="TransportProcesses",
        )
        
        queue1 = port_data.QueueData(
            ID="Q1",
            description="Queue 1",
            capacity=10,
            location=[10.0, 10.0],
            interface_type=port_data.PortInterfaceType.INPUT,
        )
        queue2 = port_data.QueueData(
            ID="Q2",
            description="Queue 2",
            capacity=10,
            location=[10.0, 10.0],
            interface_type=port_data.PortInterfaceType.OUTPUT,
        )
        
        resource = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
            ports=["Q1", "Q2"],
        )
        
        product = product_data.ProductData(
            ID="Product1",
            description="Product 1",
            type="Product1",
            processes={"P1": []},
            transport_process="TP1",
        )
        
        source = source_data.SourceData(
            ID="Source1",
            description="Source 1",
            location=[0.0, 0.0],
            product_type="Product1",
            time_model_id="tm1",
            routing_heuristic="random",
        )
        
        sink = sink_data.SinkData(
            ID="Sink1",
            description="Sink 1",
            location=[50.0, 50.0],
            product_type="Product1",
        )
        
        return ProductionSystemData(
            ID="test",
            time_model_data=[tm1],
            process_data=[process, transport],
            port_data=[queue1, queue2],
            resource_data=[resource],
            product_data=[product],
            source_data=[source],
            sink_data=[sink],
        )

    def test_add_resource_with_new_process(self, base_system):
        """Test adding a new resource with a new process."""
        # Add new time model for new process
        tm2 = time_model_data.FunctionTimeModelData(
            ID="tm2",
            description="Time model 2",
            distribution_function="constant",
            location=5.0,
            scale=0.0,
        )
        base_system.time_model_data.append(tm2)
        
        # Add new process
        process2 = processes_data.ProductionProcessData(
            ID="P2",
            description="Process 2",
            time_model_id="tm2",
            type="ProductionProcesses",
        )
        base_system.process_data.append(process2)
        
        # Add new queues
        queue3 = port_data.QueueData(
            ID="Q3",
            description="Queue 3",
            capacity=10,
            location=[20.0, 20.0],
            interface_type=port_data.PortInterfaceType.INPUT,
        )
        queue4 = port_data.QueueData(
            ID="Q4",
            description="Queue 4",
            capacity=10,
            location=[20.0, 20.0],
            interface_type=port_data.PortInterfaceType.OUTPUT,
        )
        base_system.port_data.append(queue3)
        base_system.port_data.append(queue4)
        
        # Add new resource
        resource2 = resource_data.ResourceData(
            ID="R2",
            description="Resource 2",
            location=[20.0, 20.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P2"],
            ports=["Q3", "Q4"],
        )
        base_system.resource_data.append(resource2)
        
        # Should not raise
        base_system.revalidate()
        
        assert len(base_system.resource_data) == 2
        assert len(base_system.process_data) == 3  # P1, P2, TP1

    def test_remove_resource(self, base_system):
        """Test removing a resource."""
        # Remove resource
        base_system.resource_data.remove(base_system.resource_data[0])
        
        # Should not raise validation error (resource removal is allowed)
        base_system.revalidate()
        
        assert len(base_system.resource_data) == 0

    def test_add_resource_with_invalid_process_raises_error(self, base_system):
        """Test that adding a resource with invalid process raises ValidationError."""
        # Add new queues
        queue3 = port_data.QueueData(
            ID="Q3",
            description="Queue 3",
            capacity=10,
            location=[20.0, 20.0],
            interface_type=port_data.PortInterfaceType.INPUT,
        )
        queue4 = port_data.QueueData(
            ID="Q4",
            description="Queue 4",
            capacity=10,
            location=[20.0, 20.0],
            interface_type=port_data.PortInterfaceType.OUTPUT,
        )
        base_system.port_data.append(queue3)
        base_system.port_data.append(queue4)
        
        # Add resource with invalid process
        resource2 = resource_data.ResourceData(
            ID="R2",
            description="Resource 2",
            location=[20.0, 20.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["invalid_process"],  # Invalid process
            ports=["Q3", "Q4"],
        )
        base_system.resource_data.append(resource2)
        
        with pytest.raises(ValidationError) as exc_info:
            base_system.revalidate()
        
        assert "process" in str(exc_info.value).lower()
        assert "R2" in str(exc_info.value)

    def test_add_resource_without_ports_gets_defaults(self, base_system):
        """Test that adding a resource without ports gets default ports."""
        # Add new process
        process2 = processes_data.ProductionProcessData(
            ID="P2",
            description="Process 2",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        base_system.process_data.append(process2)
        
        # Add resource without ports
        resource2 = resource_data.ResourceData(
            ID="R2",
            description="Resource 2",
            location=[20.0, 20.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P2"],
            ports=None,  # No ports
        )
        base_system.resource_data.append(resource2)
        
        # Add default queues
        from prodsys.models.production_system_data import add_default_queues_to_resources
        base_system = add_default_queues_to_resources(base_system)
        
        # Should not raise
        base_system.revalidate()
        
        assert resource2.ports is not None
        assert len(resource2.ports) >= 1  # At least one port

    def test_update_resource_processes(self, base_system):
        """Test updating resource processes."""
        # Add new process
        process2 = processes_data.ProductionProcessData(
            ID="P2",
            description="Process 2",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        base_system.process_data.append(process2)
        
        # Update resource to use new process
        base_system.resource_data[0].process_ids = ["P2"]
        
        # Should not raise
        base_system.revalidate()
        
        assert base_system.resource_data[0].process_ids == ["P2"]

    def test_update_resource_processes_invalid(self, base_system):
        """Test that updating resource with invalid process raises ValidationError."""
        # Update resource to use invalid process
        base_system.resource_data[0].process_ids = ["invalid_process"]
        
        with pytest.raises(ValidationError) as exc_info:
            base_system.revalidate()
        
        assert "process" in str(exc_info.value).lower()


class TestConfigurationValidation:
    """Tests for configuration validation methods."""

    def test_assert_no_redundant_locations(self):
        """Test that redundant locations raise ValueError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        # Two resources at same location
        resource1 = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
        )
        
        resource2 = resource_data.ResourceData(
            ID="R2",
            description="Resource 2",
            location=[10.0, 10.0],  # Same location
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
        )
        
        system = ProductionSystemData(
            ID="test",
            time_model_data=[tm1],
            process_data=[process],
            resource_data=[resource1, resource2],
        )
        
        with pytest.raises(ValueError) as exc_info:
            system.validate_configuration()
        
        assert "location" in str(exc_info.value).lower()

    def test_assert_all_links_available(self):
        """Test that invalid links raise ValueError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        # Link transport process with invalid link
        link_transport = processes_data.LinkTransportProcessData(
            ID="LTP1",
            description="Link Transport 1",
            time_model_id="tm1",
            type="LinkTransportProcesses",
            links=[["invalid_location", "R1"]],  # Invalid start location
        )
        
        node = node_data.NodeData(
            ID="N1",
            description="Node 1",
            location=[10.0, 10.0],
        )
        
        resource = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[20.0, 20.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["LTP1"],
        )
        
        system = ProductionSystemData(
            ID="test",
            time_model_data=[tm1],
            process_data=[link_transport],
            node_data=[node],
            resource_data=[resource],
        )
        
        with pytest.raises(ValueError) as exc_info:
            system.validate_configuration()
        
        assert "link" in str(exc_info.value).lower()
        assert "invalid_location" in str(exc_info.value)

    def test_assert_ports_have_locations(self):
        """Test that ports without locations raise ValueError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        # Port without location
        queue = port_data.QueueData(
            ID="Q1",
            description="Queue 1",
            capacity=10,
            location=None,  # No location
            interface_type=port_data.PortInterfaceType.INPUT,
        )
        
        # Output port with location (required for resource)
        queue2 = port_data.QueueData(
            ID="Q2",
            description="Queue 2",
            capacity=10,
            location=[10.0, 10.0],
            interface_type=port_data.PortInterfaceType.OUTPUT,
        )
        
        resource = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
            ports=["Q1", "Q2"],
        )
        
        system = ProductionSystemData(
            ID="test",
            time_model_data=[tm1],
            process_data=[process],
            port_data=[queue, queue2],
            resource_data=[resource],
        )
        
        with pytest.raises(ValueError) as exc_info:
            system.validate_configuration()
        
        assert "location" in str(exc_info.value).lower()
        assert "Q1" in str(exc_info.value)

    def test_assert_required_processes_in_resources_available(self):
        """Test that missing required processes raise ValueError."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        transport = processes_data.TransportProcessData(
            ID="TP1",
            description="Transport 1",
            time_model_id="tm1",
            type="TransportProcesses",
        )
        
        # Add P2 process but don't assign it to any resource
        process2 = processes_data.ProductionProcessData(
            ID="P2",
            description="Process 2",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        # Product requires P2, but no resource provides it
        product = product_data.ProductData(
            ID="Product1",
            description="Product 1",
            type="Product1",
            processes={"P2": []},  # P2 not available in resources
            transport_process="TP1",
        )
        
        resource = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],  # Only P1, not P2
        )
        
        system = ProductionSystemData(
            ID="test",
            time_model_data=[tm1],
            process_data=[process, process2, transport],
            resource_data=[resource],
            product_data=[product],
        )
        
        with pytest.raises(ValueError) as exc_info:
            system.validate_configuration()
        
        assert "process" in str(exc_info.value).lower()
        assert "P2" in str(exc_info.value) or "not available" in str(exc_info.value).lower()

    def test_valid_configuration_passes(self):
        """Test that a valid configuration passes all validations."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        transport = processes_data.TransportProcessData(
            ID="TP1",
            description="Transport 1",
            time_model_id="tm1",
            type="TransportProcesses",
        )
        
        queue1 = port_data.QueueData(
            ID="Q1",
            description="Queue 1",
            capacity=10,
            location=[10.0, 10.0],
            interface_type=port_data.PortInterfaceType.INPUT,
        )
        queue2 = port_data.QueueData(
            ID="Q2",
            description="Queue 2",
            capacity=10,
            location=[10.0, 10.0],
            interface_type=port_data.PortInterfaceType.OUTPUT,
        )
        
        resource = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
            ports=["Q1", "Q2"],
        )
        
        # Add transport resource for TP1
        transport_resource = resource_data.ResourceData(
            ID="TR1",
            description="Transport Resource 1",
            location=[5.0, 5.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["TP1"],
        )
        
        product = product_data.ProductData(
            ID="Product1",
            description="Product 1",
            type="Product1",
            processes={"P1": []},
            transport_process="TP1",
        )
        
        source = source_data.SourceData(
            ID="Source1",
            description="Source 1",
            location=[0.0, 0.0],
            product_type="Product1",
            time_model_id="tm1",
            routing_heuristic="random",
        )
        
        sink = sink_data.SinkData(
            ID="Sink1",
            description="Sink 1",
            location=[50.0, 50.0],
            product_type="Product1",
        )
        
        system = ProductionSystemData(
            ID="test",
            time_model_data=[tm1],
            process_data=[process, transport],
            port_data=[queue1, queue2],
            resource_data=[resource, transport_resource],
            product_data=[product],
            source_data=[source],
            sink_data=[sink],
        )
        
        # Should not raise
        system.validate_configuration()
        
        assert system.valid_configuration is True


class TestScheduleValidation:
    """Tests for schedule validation."""

    def test_check_schedule_invalid_resource(self):
        """Test that schedule with invalid resource raises ValidationError."""
        from prodsys.models.performance_data import Event
        
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        transport = processes_data.TransportProcessData(
            ID="TP1",
            description="Transport 1",
            time_model_id="tm1",
            type="TransportProcesses",
        )
        
        resource = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
        )
        
        product = product_data.ProductData(
            ID="Product1",
            description="Product 1",
            type="Product1",
            processes={"P1": []},
            transport_process="TP1",
        )
        
        # Event with invalid resource
        event = Event(
            resource="invalid_resource",
            product="Product1_1",
            process="P1",
            activity="start state",
            state_type="Production",
            time=0.0,
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                process_data=[process, transport],
                resource_data=[resource],
                product_data=[product],
                schedule=[event],
            )
        
        assert "resource" in str(exc_info.value).lower()
        assert "schedule" in str(exc_info.value).lower()

    def test_check_schedule_invalid_process(self):
        """Test that schedule with invalid process raises ValidationError."""
        from prodsys.models.performance_data import Event
        
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        transport = processes_data.TransportProcessData(
            ID="TP1",
            description="Transport 1",
            time_model_id="tm1",
            type="TransportProcesses",
        )
        
        resource = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
        )
        
        product = product_data.ProductData(
            ID="Product1",
            description="Product 1",
            type="Product1",
            processes={"P1": []},
            transport_process="TP1",
        )
        
        # Event with invalid process
        event = Event(
            resource="R1",
            product="Product1_1",
            process="invalid_process",
            activity="start state",
            state_type="Production",
            time=0.0,
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                process_data=[process, transport],
                resource_data=[resource],
                product_data=[product],
                schedule=[event],
            )
        
        assert "process" in str(exc_info.value).lower()
        assert "schedule" in str(exc_info.value).lower()

    def test_check_schedule_invalid_product(self):
        """Test that schedule with invalid product raises ValidationError."""
        from prodsys.models.performance_data import Event
        
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        transport = processes_data.TransportProcessData(
            ID="TP1",
            description="Transport 1",
            time_model_id="tm1",
            type="TransportProcesses",
        )
        
        resource = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
        )
        
        product = product_data.ProductData(
            ID="Product1",
            description="Product 1",
            type="Product1",
            processes={"P1": []},
            transport_process="TP1",
        )
        
        # Event with invalid product (Product2 doesn't exist)
        event = Event(
            resource="R1",
            product="Product2_1",  # Invalid product
            process="P1",
            activity="start state",
            state_type="Production",
            time=0.0,
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ProductionSystemData(
                ID="test",
                time_model_data=[tm1],
                process_data=[process, transport],
                resource_data=[resource],
                product_data=[product],
                schedule=[event],
            )
        
        assert "product" in str(exc_info.value).lower()
        assert "schedule" in str(exc_info.value).lower()


class TestDefaultQueueCreation:
    """Tests for automatic default queue creation for resources."""
    
    def test_production_resource_gets_default_queues(self):
        """Test that a production resource without ports gets default queues automatically."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        resource = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
            ports=None,  # No ports specified
        )
        
        system = ProductionSystemData(
            ID="test",
            time_model_data=[tm1],
            process_data=[process],
            resource_data=[resource],
        )
        
        # Resource should have default queues added
        assert resource.ports is not None
        assert len(resource.ports) == 1
        assert f"{resource.ID}_default_queue" in resource.ports
        
        # Queues should be in port_data
        port_ids = [p.ID for p in system.port_data]
        assert f"{resource.ID}_default_queue" in port_ids
    
    def test_transport_resource_no_queues(self):
        """Test that a transport resource with only transport processes doesn't get queues."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        transport = processes_data.TransportProcessData(
            ID="TP1",
            description="Transport 1",
            time_model_id="tm1",
            type="TransportProcesses",
        )
        
        resource = resource_data.ResourceData(
            ID="TR1",
            description="Transport Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["TP1"],
            ports=None,  # No ports specified
        )
        
        system = ProductionSystemData(
            ID="test",
            time_model_data=[tm1],
            process_data=[transport],
            resource_data=[resource],
        )
        
        # Transport resource should not have queues added automatically
        assert resource.ports is None or len(resource.ports) == 0
        
        # No default queues should be in port_data for this resource
        port_ids = [p.ID for p in system.port_data]
        assert f"{resource.ID}_default_input_queue" not in port_ids
        assert f"{resource.ID}_default_output_queue" not in port_ids
        assert f"{resource.ID}_default_queue" not in port_ids
    
    def test_mixed_process_resource_gets_queues(self):
        """Test that a resource with both production and transport processes gets queues."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        transport = processes_data.TransportProcessData(
            ID="TP1",
            description="Transport 1",
            time_model_id="tm1",
            type="TransportProcesses",
        )
        
        resource = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1", "TP1"],  # Both production and transport
            ports=None,  # No ports specified
        )
        
        system = ProductionSystemData(
            ID="test",
            time_model_data=[tm1],
            process_data=[process, transport],
            resource_data=[resource],
        )
        
        # Resource should have default queues added (has production process)
        assert resource.ports is not None
        assert len(resource.ports) == 1
        assert f"{resource.ID}_default_queue" in resource.ports
    
    def test_resource_with_existing_ports_no_auto_creation(self):
        """Test that a resource with existing ports doesn't get additional default queues."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        queue1 = port_data.QueueData(
            ID="Q1",
            description="Queue 1",
            capacity=10,
            location=[10.0, 10.0],
            interface_type=port_data.PortInterfaceType.INPUT,
        )
        queue2 = port_data.QueueData(
            ID="Q2",
            description="Queue 2",
            capacity=10,
            location=[10.0, 10.0],
            interface_type=port_data.PortInterfaceType.OUTPUT,
        )
        
        resource = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
            ports=["Q1", "Q2"],  # Ports already specified
        )
        
        system = ProductionSystemData(
            ID="test",
            time_model_data=[tm1],
            process_data=[process],
            port_data=[queue1, queue2],
            resource_data=[resource],
        )
        
        # Resource should keep its existing ports
        assert resource.ports == ["Q1", "Q2"]
        
        # No default queues should be created
        port_ids = [p.ID for p in system.port_data]
        assert f"{resource.ID}_default_input_queue" not in port_ids
        assert f"{resource.ID}_default_output_queue" not in port_ids
    
    def test_multiple_resources_get_default_queues(self):
        """Test that multiple production resources without ports all get default queues."""
        tm1 = time_model_data.FunctionTimeModelData(
            ID="tm1",
            description="Time model 1",
            distribution_function="constant",
            location=10.0,
            scale=0.0,
        )
        
        process = processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type="ProductionProcesses",
        )
        
        resource1 = resource_data.ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
            ports=None,
        )
        
        resource2 = resource_data.ResourceData(
            ID="R2",
            description="Resource 2",
            location=[20.0, 20.0],
            capacity=1,
            controller="PipelineController",
            control_policy="FIFO",
            process_ids=["P1"],
            ports=None,
        )
        
        system = ProductionSystemData(
            ID="test",
            time_model_data=[tm1],
            process_data=[process],
            resource_data=[resource1, resource2],
        )
        
        # Both resources should have default queues
        assert resource1.ports is not None
        assert len(resource1.ports) == 1
        assert resource2.ports is not None
        assert len(resource2.ports) == 1
        
        # All queues should be in port_data
        port_ids = [p.ID for p in system.port_data]
        assert f"{resource1.ID}_default_queue" in port_ids
        assert f"{resource2.ID}_default_queue" in port_ids


class TestDependencySerialization:
    """Tests for dependency data serialization and deserialization."""

    def test_dependency_serialization_deserialization(self):
        """Test that dependency data is correctly serialized and deserialized."""
        import json
        import tempfile
        import os
        import prodsys.express as psx
        from prodsys.models.dependency_data import ProcessDependencyData, ResourceDependencyData

        # Create time models
        t1 = psx.FunctionTimeModel("normal", 1, 0.1, "t1")
        t2 = psx.FunctionTimeModel("normal", 2, 0.2, "t2")
        t3 = psx.DistanceTimeModel(speed=180, reaction_time=0.1, ID="t3")

        # Create processes
        p1 = psx.ProductionProcess(t1, "p1")
        p2 = psx.ProductionProcess(t2, "p2")
        tp = psx.TransportProcess(t3, "tp")
        move_p = psx.TransportProcess(t3, "move")
        assembly_process = psx.ProductionProcess(
            psx.FunctionTimeModel("exponential", 0.1, ID="assembly_time"),
            "assembly_process"
        )

        # Create setup states
        s1 = psx.FunctionTimeModel("exponential", 0.5, ID="s1")
        setup_state_1 = psx.SetupState(s1, p1, p2, "S1")
        setup_state_2 = psx.SetupState(s1, p2, p1, "S2")

        # Create resources
        worker = psx.Resource([move_p, assembly_process], [2, 0], 1, ID="worker")
        worker2 = psx.Resource([move_p, assembly_process], [3, 0], 1, ID="worker2")
        transport = psx.Resource([tp], [2, 2], 1, ID="transport")

        # Create interaction nodes
        interaction_node_assembly = psx.Node(location=[5, 6], ID="interaction_node_assembly")
        interaction_node_resource_2 = psx.Node(location=[7, 4], ID="interaction_node_resource_2")

        # Create dependencies
        assembly_dependency = psx.ProcessDependency(
            ID="assembly_dependency",
            required_process=assembly_process,
            interaction_node=interaction_node_assembly,
        )
        resource_2_dependency = psx.ResourceDependency(
            ID="resource_2_dependency",
            required_resource=worker2,
            interaction_node=interaction_node_resource_2,
        )

        # Create resources with dependencies
        machine = psx.Resource(
            [p1, p2],
            [5, 5],
            1,
            states=[setup_state_1, setup_state_2],
            ID="machine",
            dependencies=[assembly_dependency],
        )
        machine2 = psx.Resource(
            [p1, p2],
            [7, 2],
            3,
            states=[setup_state_1, setup_state_2],
            ID="machine2",
            dependencies=[resource_2_dependency],
        )

        # Create products
        product1 = psx.Product(process=[p1], transport_process=tp, ID="product1")
        product2 = psx.Product(process=[p2], transport_process=tp, ID="product2")

        # Create sources and sinks
        arrival_model_1 = psx.FunctionTimeModel("exponential", 2, ID="arrival_model_1")
        arrival_model_2 = psx.FunctionTimeModel("exponential", 4, ID="arrival_model_2")
        source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")
        source2 = psx.Source(product2, arrival_model_2, [0, 0], ID="source_2")
        sink1 = psx.Sink(product1, [10, 0], "sink1")
        sink2 = psx.Sink(product2, [10, 0], "sink2")

        # Create production system
        system = psx.ProductionSystem(
            [machine, machine2, transport, worker, worker2],
            [source1, source2],
            [sink1, sink2],
        )

        # Convert to ProductionSystemData model
        model = system.to_model()

        # Verify original dependency data
        assert len(model.dependency_data) == 2
        original_dependency_ids = {dep.ID for dep in model.dependency_data}
        assert "assembly_dependency" in original_dependency_ids
        assert "resource_2_dependency" in original_dependency_ids

        # Check that dependencies are present in resource data
        machine_resource = next(r for r in model.resource_data if r.ID == "machine")
        assert machine_resource.dependency_ids == ["assembly_dependency"]
        machine2_resource = next(r for r in model.resource_data if r.ID == "machine2")
        assert machine2_resource.dependency_ids == ["resource_2_dependency"]

        # Serialize to JSON
        json_str = model.model_dump_json(indent=2)
        json_dict = json.loads(json_str)
        assert len(json_dict.get("dependency_data", [])) == 2

        # Deserialize from JSON
        deserialized_model = ProductionSystemData.model_validate(json_dict)

        # Verify deserialized dependency data
        assert len(deserialized_model.dependency_data) == 2
        deserialized_dependency_ids = {dep.ID for dep in deserialized_model.dependency_data}
        assert deserialized_dependency_ids == original_dependency_ids

        # Verify each dependency in detail
        for orig_dep in model.dependency_data:
            deser_dep = next(
                (d for d in deserialized_model.dependency_data if d.ID == orig_dep.ID),
                None
            )
            assert deser_dep is not None, f"Dependency '{orig_dep.ID}' not found in deserialized data"
            assert orig_dep.dependency_type == deser_dep.dependency_type

            # Verify dependency-specific fields
            if isinstance(orig_dep, ProcessDependencyData):
                assert orig_dep.required_process == deser_dep.required_process
                assert orig_dep.interaction_node == deser_dep.interaction_node
            elif isinstance(orig_dep, ResourceDependencyData):
                assert orig_dep.required_resource == deser_dep.required_resource
                assert orig_dep.interaction_node == deser_dep.interaction_node

        # Verify resource dependency references are preserved
        deserialized_machine = next(r for r in deserialized_model.resource_data if r.ID == "machine")
        assert deserialized_machine.dependency_ids == machine_resource.dependency_ids
        deserialized_machine2 = next(r for r in deserialized_model.resource_data if r.ID == "machine2")
        assert deserialized_machine2.dependency_ids == machine2_resource.dependency_ids

    def test_dependency_file_io(self):
        """Test that dependency data is correctly preserved when writing to and reading from file."""
        import tempfile
        import os
        import prodsys.express as psx

        # Create a simple system with dependencies
        t1 = psx.FunctionTimeModel("normal", 1, 0.1, "t1")
        p1 = psx.ProductionProcess(t1, "p1")
        tp = psx.TransportProcess(psx.DistanceTimeModel(speed=180, reaction_time=0.1, ID="t3"), "tp")
        assembly_process = psx.ProductionProcess(
            psx.FunctionTimeModel("exponential", 0.1, ID="assembly_time"),
            "assembly_process"
        )
        worker = psx.Resource([assembly_process], [2, 0], 1, ID="worker")
        interaction_node = psx.Node(location=[5, 6], ID="interaction_node_assembly")
        assembly_dependency = psx.ProcessDependency(
            ID="assembly_dependency",
            required_process=assembly_process,
            interaction_node=interaction_node,
        )
        machine = psx.Resource(
            [p1],
            [5, 5],
            1,
            ID="machine",
            dependencies=[assembly_dependency],
        )
        transport = psx.Resource([tp], [2, 2], 1, ID="transport")
        product1 = psx.Product(process=[p1], transport_process=tp, ID="product1")
        source1 = psx.Source(
            product1,
            psx.FunctionTimeModel("exponential", 2, ID="arrival_model_1"),
            [0, 0],
            ID="source_1"
        )
        sink1 = psx.Sink(product1, [10, 0], "sink1")

        system = psx.ProductionSystem(
            [machine, transport, worker],
            [source1],
            [sink1],
        )

        model = system.to_model()
        original_dependency_count = len(model.dependency_data)

        # Write to file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            model.write(tmp_path)

            # Read from file
            loaded_model = ProductionSystemData.read(tmp_path)

            # Verify loaded dependency data
            assert len(loaded_model.dependency_data) == original_dependency_count
            loaded_dependency_ids = {dep.ID for dep in loaded_model.dependency_data}
            original_dependency_ids = {dep.ID for dep in model.dependency_data}
            assert loaded_dependency_ids == original_dependency_ids

            # Verify resource dependencies are preserved
            for orig_resource in model.resource_data:
                if orig_resource.dependency_ids:
                    loaded_resource = next(
                        (r for r in loaded_model.resource_data if r.ID == orig_resource.ID),
                        None
                    )
                    assert loaded_resource is not None
                    assert orig_resource.dependency_ids == loaded_resource.dependency_ids

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_none_dependency_data_handling(self):
        """Test that None dependency_data is handled correctly."""
        import prodsys.express as psx

        # Create a simple system
        t1 = psx.FunctionTimeModel("normal", 1, 0.1, "t1")
        p1 = psx.ProductionProcess(t1, "p1")
        tp = psx.TransportProcess(psx.DistanceTimeModel(speed=180, reaction_time=0.1, ID="t3"), "tp")
        transport = psx.Resource([tp], [2, 2], 1, ID="transport")
        machine = psx.Resource([p1], [5, 5], 1, ID="machine")  # Resource that provides p1
        product1 = psx.Product(process=[p1], transport_process=tp, ID="product1")
        source1 = psx.Source(
            product1,
            psx.FunctionTimeModel("exponential", 2, ID="arrival_model_1"),
            [0, 0],
            ID="source_1"
        )
        sink1 = psx.Sink(product1, [10, 0], "sink1")

        system = psx.ProductionSystem([machine, transport], [source1], [sink1])
        model = system.to_model()

        # Test with None dependency_data
        model_dict = model.model_dump()
        model_dict['dependency_data'] = None
        model_with_none = ProductionSystemData.model_validate(model_dict)

        # Should default to empty list or None
        assert model_with_none.dependency_data is None or len(model_with_none.dependency_data) == 0

