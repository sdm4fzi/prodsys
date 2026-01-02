#!/usr/bin/env python3
"""
Simple example demonstrating ProcessModel and SystemResource features.

This script shows the basic functionality without complex dependencies.
"""

import prodsys.express as psx

def main():
    """Main example function."""
    print("=== Simple ProcessModel and SystemResource Example ===\n")
    
    # 1. Create time models
    print("1. Creating time models...")
    tm_weld = psx.FunctionTimeModel("normal", 20.0, 5.0, "tm_weld")
    tm_assembly = psx.FunctionTimeModel("normal", 15.0, 3.0, "tm_assembly")
    tm_transport = psx.DistanceTimeModel(60, 0.1, "manhattan", "tm_transport")
    print("   ✓ Time models created")
    
    # 2. Create individual processes
    print("\n2. Creating individual processes...")
    weld_process = psx.ProductionProcess(tm_weld, "weld")
    assembly_process = psx.ProductionProcess(tm_assembly, "assembly")
    transport_process = psx.TransportProcess(tm_transport, "transport")
    print("   ✓ Individual processes created")
    
    # 3. Create SequentialProcess (auto-generates adjacency matrix)
    print("\n3. Creating SequentialProcess...")
    sequential_process = psx.SequentialProcess(
        time_model=psx.FunctionTimeModel("constant", 0.0, ID="tm_seq"),
        process_ids=["weld", "assembly"],
        ID="sequential_process"
    )
    print(f"   ✓ SequentialProcess created")
    print(f"   ✓ Adjacency matrix: {sequential_process.adjacency_matrix}")
    
    # 4. Create ProcessModel (DAG)
    print("\n4. Creating ProcessModel (DAG)...")
    process_model = psx.ProcessModel(
        time_model=psx.FunctionTimeModel("constant", 0.0, ID="tm_pm"),
        process_ids=["weld", "assembly"],
        adjacency_matrix={
            "weld": ["assembly"],
            "assembly": []
        },
        ID="process_model"
    )
    print("   ✓ ProcessModel created")
    
    # 5. Create LoadingProcess
    print("\n5. Creating LoadingProcess...")
    loading_process = psx.LoadingProcess(
        time_model=psx.FunctionTimeModel("normal", 2.0, 0.5, ID="tm_loading"),
        dependency_type="before",
        can_be_chained=True,
        ID="loading_process"
    )
    print("   ✓ LoadingProcess created")
    
    # 6. Create regular resources
    print("\n6. Creating regular resources...")
    machine1 = psx.Resource([weld_process], [5, 0], 1, ID="machine1")
    machine2 = psx.Resource([assembly_process], [10, 0], 1, ID="machine2")
    transport_resource = psx.Resource([transport_process], [0, 0], 1, ID="transport")
    print("   ✓ Regular resources created")
    
    # 7. Create SystemResource (simplified)
    print("\n7. Creating SystemResource...")
    system_resource = psx.SystemResource(
        processes=[sequential_process],
        location=[20, 5],
        sub_resources=[machine1, machine2],
        ID="system_resource"
    )
    print("   ✓ SystemResource created")
    
    # 8. Create Product with ProcessModel
    print("\n8. Creating Product with ProcessModel...")
    product = psx.Product(
        process=sequential_process,
        transport_process=transport_process,
        ID="product"
    )
    print("   ✓ Product created")
    
    # 9. Test data model conversion
    print("\n9. Testing data model conversion...")
    try:
        # Convert to data models
        seq_data = sequential_process.to_model()
        pm_data = process_model.to_model()
        lp_data = loading_process.to_model()
        sr_data = system_resource.to_model()
        product_data = product.to_model()
        
        print("   ✓ All objects converted to data models")
        print(f"   ✓ SequentialProcess data: ID={seq_data.ID}, process_ids={seq_data.process_ids}")
        print(f"   ✓ ProcessModel data: ID={pm_data.ID}, process_ids={pm_data.process_ids}")
        print(f"   ✓ LoadingProcess data: ID={lp_data.ID}, dependency_type={lp_data.dependency_type}")
        print(f"   ✓ SystemResource data: ID={sr_data.ID}, subresource_ids={sr_data.subresource_ids}")
        print(f"   ✓ Product data: ID={product_data.ID}, processes={product_data.processes}")
        
    except Exception as e:
        print(f"   ✗ Error converting to data model: {e}")
    
    print("\n=== Example completed successfully! ===")
    print("\nKey features demonstrated:")
    print("- ProcessModel: DAG-based process execution")
    print("- SequentialProcess: Auto-generated sequential execution")
    print("- LoadingProcess: Dependency-based loading")
    print("- SystemResource: Hierarchical resource with subresources")
    print("- Product: Uses ProcessModel as its process")

if __name__ == "__main__":
    main()
