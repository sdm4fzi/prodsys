#!/usr/bin/env python3
"""
Example demonstrating a manufacturing cell (SystemResource) with a robot and two machines.

This script shows:
1. How to create a SystemResource representing a manufacturing cell
2. A robot that loads/unloads products to/from the cell ports
3. Two machines that can process products (either one can be used - parallel choice)
4. ProcessModel with adjacency matrix showing parallel process execution
5. AGV transport in the global system
"""

import prodsys.express as psx


def main():
    """Main example function."""
    print("=== System Resource with Robot and Machines Example ===\n")
    
    # ========== TIME MODELS ==========
    print("1. Creating time models...")
    
    # Robot time models
    tm_robot_handling = psx.FunctionTimeModel(
        distribution_function="normal",
        location=5.0,
        scale=1.0,
        ID="tm_robot_load"
    )
    
    # Machine time models
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
    
    # Transport and system time models
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
    
    print("   ✓ Time models created")
    
    # ========== PROCESSES ==========
    print("\n2. Creating processes...")
    
    # Robot processes
    robot_handling_process = psx.TransportProcess(
        time_model=tm_robot_handling,
        ID="robot_handling"
    )
    
    # Machine processes
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
    
    # Transport process
    agv_transport = psx.TransportProcess(
        time_model=tm_agv,
        ID="agv_transport"
    )
    
    print("   ✓ Individual processes created")
    
    # ========== PROCESS MODEL ==========
    print("\n3. Creating ProcessModel with parallel execution...")
    
    # Create ProcessModel with adjacency matrix
    # Workflow: robot_load → (machine1 OR machine2) → robot_unload
    # The adjacency matrix allows parallel choice between machine1 and machine2
    cell_process_model = psx.ProcessModel(
        adjacency_matrix={
            "machine1_process": ["machine2_process"],
            "machine2_process": []
        },
        ID="cell_process_model"
    )
    
    print("   ✓ ProcessModel created with adjacency matrix:")
    print(f"      {cell_process_model.adjacency_matrix}")

    product_process_model = psx.ProcessModel(
        can_contain_other_models=True,
        ID="product_process_model",
        adjacency_matrix={
            "machine3_process": ["cell_process_model"],
            "cell_process_model": []
        }
    )
    
    # ========== RESOURCES ==========
    print("\n4. Creating resources...")
    
    # Robot resource for loading/unloading
    robot = psx.Resource(
        # processes=[robot_handling_process], # TODO: use later capability processes hor multiple different processes
        processes=[agv_transport],
        location=[12, 10],  # Inside the cell
        capacity=1,
        ID="robot"
    )
    
    # Machine resources
    machine1 = psx.Resource(
        processes=[machine1_process],
        location=[12, 8],  # Inside the cell
        capacity=1,
        ID="machine1"
    )
    machine2 = psx.Resource(
        processes=[machine2_process],
        location=[12, 12],  # Inside the cell
        capacity=1,
        ID="machine2"
    )

    machine3 = psx.Resource(
        processes=[machine3_process],
        location=[12, 16],  # Inside the cell
        capacity=1,
        ID="machine3"
    )
    
    # AGV for global transport
    agv = psx.Resource(
        processes=[agv_transport],
        location=[0, 10],
        capacity=1,
        ID="agv"
    )
    
    print("   ✓ Robot, machines, and AGV created")
    
    # ========== SYSTEM RESOURCE (CELL) ==========
    print("\n5. Creating SystemResource (manufacturing cell)...")
    
    # Create the manufacturing cell as a SystemResource
    # The cell contains the robot and two machines
    manufacturing_cell = psx.SystemResource(
        processes=[cell_process_model],
        location=[10, 10],
        subresource_ids=["robot", "machine1", "machine2"],
        capacity=5,  # One product can be in the system at a time
        ID="manufacturing_cell"
    )
    
    print("   ✓ Manufacturing cell (SystemResource) created")
    print(f"      Subresources: {manufacturing_cell.subresource_ids}")
    
    # ========== PRODUCT ==========
    print("\n6. Creating product...")
    
    product = psx.Product(
        process=product_process_model,
        transport_process=agv_transport,
        ID="product"
    )
    
    print("   ✓ Product created with ProcessModel")
    
    # ========== SOURCES AND SINKS ==========
    print("\n7. Creating sources and sinks...")
    
    source = psx.Source(product, tm_arrival, [0, 10], ID="source")
    
    sink = psx.Sink(product, [20, 10], ID="sink")
    
    print("   ✓ Source and sink created")
    
    # ========== PRODUCTION SYSTEM ==========
    print("\n8. Creating ProductionSystem...")
    
    system = psx.ProductionSystem(
        resources=[robot, machine1, machine2, machine3, manufacturing_cell, agv],
        sources=[source],
        sinks=[sink],
        ID="production_system"
    )
    
    print("   ✓ ProductionSystem created")
    
    # ========== VALIDATION AND SIMULATION ==========
    print("\n9. Validating and running simulation...")
    
    system.validate()
    print("   ✓ System validated successfully")
    system_data = system.to_model()
    system_data.write("examples/modelling_and_simulation/simulation_example_data/system_resource_with_robot_example.json")
    
    # Run simulation
    system.run(time_range=1000)
    print("   ✓ Simulation completed")
    
    # Print results
    print("\n10. Simulation Results:")
    system.runner.print_results()
    system.runner.save_results_as_csv()

if __name__ == "__main__":
    main()

