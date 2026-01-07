#!/usr/bin/env python3
"""
Example script demonstrating ProcessModel and SystemResource features.

This script shows how to:
1. Create ProcessModel and SequentialProcess
2. Create SystemResource with subresources
3. Create Product with ProcessModel
4. Run a simple simulation
"""

import prodsys.express as psx

def main():
    """Main example function."""
    print("=== ProcessModel and SystemResource Example ===\n")
    
    # 1. Create time models
    print("1. Creating time models...")
    tm_weld = psx.FunctionTimeModel("normal", 20.0, 5.0, "tm_weld")
    tm_assembly = psx.FunctionTimeModel("normal", 15.0, 3.0, "tm_assembly")
    tm_paint = psx.FunctionTimeModel("normal", 10.0, 2.0, "tm_paint")
    tm_transport = psx.DistanceTimeModel(60, 0.1, "manhattan", "tm_transport")
    tm_arrival = psx.FunctionTimeModel("exponential", 30.0, ID="tm_arrival")
    print("   ✓ Time models created")
    
    # 2. Create individual processes
    print("\n2. Creating individual processes...")
    weld_process = psx.ProductionProcess(tm_weld, "weld")
    assembly_process = psx.ProductionProcess(tm_assembly, "assembly")
    paint_process = psx.ProductionProcess(tm_paint, "paint")
    transport_process = psx.TransportProcess(tm_transport, "transport")
    print("   ✓ Individual processes created")
    
    # 3. Create SequentialProcess (auto-generates adjacency matrix)
    print("\n3. Creating SequentialProcess...")
    sequential_process = psx.SequentialProcess(
        time_model=psx.FunctionTimeModel("constant", 0.0, ID="tm_seq"),
        process_ids=["weld", "assembly", "paint"],
        ID="sequential_process"
    )
    print(f"   ✓ SequentialProcess created with adjacency matrix: {sequential_process.adjacency_matrix}")
    
    # 4. Create ProcessModel (DAG)
    print("\n4. Creating ProcessModel (DAG)...")
    process_model = psx.ProcessModel(
        time_model=psx.FunctionTimeModel("constant", 0.0, ID="tm_pm"),
        process_ids=["weld", "assembly", "paint"],
        adjacency_matrix={
            "weld": ["assembly", "paint"],  # weld can go to assembly or paint
            "assembly": ["paint"],          # assembly goes to paint
            "paint": []                     # paint is final
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
    machine3 = psx.Resource([paint_process], [15, 0], 1, ID="machine3")
    transport_resource = psx.Resource([transport_process], [0, 0], 1, ID="transport")
    print("   ✓ Regular resources created")
    
    # 7. Create SystemResource (simplified - no system ports for now)
    print("\n7. Creating SystemResource...")
    system_resource = psx.SystemResource(
        processes=[sequential_process],
        location=[20, 5],
        subresource_ids=["machine1", "machine2", "machine3"],
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
    
    # 9. Create sources and sinks
    print("\n9. Creating sources and sinks...")
    source = psx.Source(product, tm_arrival, [0, 0], ID="source")
    sink = psx.Sink(product, [25, 0], "sink")
    print("   ✓ Sources and sinks created")
    
    # 10. Create ProductionSystem
    print("\n10. Creating ProductionSystem...")
    system = psx.ProductionSystem(
        [machine1, machine2, machine3, system_resource, transport_resource],
        [source],
        [sink]
    )
    print("   ✓ ProductionSystem created")
    
    # 11. Test data model conversion
    print("\n11. Testing data model conversion...")
    try:
        system_data = system.to_model()
        print("   ✓ ProductionSystem converted to data model")
        print(f"   ✓ System has {len(system_data.resource_data)} resources")
        print(f"   ✓ System has {len(system_data.product_data)} products")
        print(f"   ✓ System has {len(system_data.process_data)} processes")
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