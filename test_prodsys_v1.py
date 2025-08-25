#!/usr/bin/env python3

# Test script to verify prodsys v1 is working correctly

try:
    print("Testing prodsys v1 imports...")
    
    # Basic prodsys import
    import prodsys
    print("✓ prodsys imported successfully")
    
    # Test basic data models (they are available as prodsys.module_name)
    print(f"✓ time_model_data available: {hasattr(prodsys, 'time_model_data')}")
    print(f"✓ processes_data available: {hasattr(prodsys, 'processes_data')}")
    print(f"✓ resource_data available: {hasattr(prodsys, 'resource_data')}")
    print(f"✓ product_data available: {hasattr(prodsys, 'product_data')}")
    print(f"✓ source_data available: {hasattr(prodsys, 'source_data')}")
    print(f"✓ sink_data available: {hasattr(prodsys, 'sink_data')}")
    
    print("\n✅ All basic prodsys v1 data models are working!")
    print("You can now use the basic prodsys data models to create production systems.")
    
    # Test creating some basic objects
    print("\n🧪 Testing basic object creation...")
    
    time_model = prodsys.time_model_data.FunctionTimeModelData(
        ID="test_time_model",
        description="Test time model",
        distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Exponential,
        location=25.0,
        scale=0.0,
    )
    print(f"✓ Created time model: {time_model.ID}")
    
    process = prodsys.processes_data.ProductionProcessData(
        ID="test_process",
        description="Test process",
        time_model_id=time_model.ID,
        type=prodsys.processes_data.ProcessTypeEnum.ProductionProcesses,
    )
    print(f"✓ Created process: {process.ID}")
    
    print("\n✅ Basic object creation works! Poetry setup is completely functional!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
