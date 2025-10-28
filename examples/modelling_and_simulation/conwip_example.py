"""
Example demonstrating CONWIP (Constant Work In Process) control in prodsys.

This example shows how to:
1. Load a configuration with CONWIP control
2. Run a simulation where product release is limited by WIP
3. Analyze how CONWIP affects system performance
"""

from prodsys.models import production_system_data
from prodsys.simulation import runner


def main():
    """
    Run a simulation with CONWIP-based product release control.
    
    CONWIP limits the number of products that can be in the system simultaneously.
    The source will only release new products when the number of products in the
    system is below the CONWIP limit.
    """
    # Load the configuration with CONWIP
    config = production_system_data.ProductionSystemData.parse_file(
        "examples/modelling_and_simulation/simulation_example_data/conwip_example.json"
    )
    
    print("Configuration loaded successfully!")
    print(f"CONWIP limit: {config.conwip_number}")
    
    # Create and run the simulation
    print("\nRunning simulation with CONWIP control...")
    sim_runner = runner.Runner(production_system_data=config)
    sim_runner.initialize_simulation()
    sim_runner.run(200)  # Run for 200 time units
    
    # Get performance results
    performance = sim_runner.get_performance_data()
    
    print("\nSimulation completed!")
    print(f"Number of events in event log: {len(performance.event_log)}")
    
    # Analyze WIP levels
    wip_kpis = [kpi for kpi in performance.kpis if kpi.name.value == "WIP"]
    if wip_kpis:
        print("\nWIP KPIs:")
        for kpi in wip_kpis:
            print(f"  {kpi.product_type if hasattr(kpi, 'product_type') else 'System'}: {kpi.value:.2f}")
            print(f"  CONWIP limit: {config.conwip_number}")
            if kpi.value <= config.conwip_number:
                print("  ✓ WIP is within CONWIP limit")
            else:
                print("  ⚠ WIP exceeded CONWIP limit (expected due to processing in progress)")
    
    # Analyze throughput
    throughput_kpis = [kpi for kpi in performance.kpis if kpi.name.value == "throughput"]
    if throughput_kpis:
        print("\nThroughput KPIs:")
        for kpi in throughput_kpis:
            print(f"  {kpi.product_type if hasattr(kpi, 'product_type') else 'System'}: {kpi.value:.2f}")
    
    # Analyze product releases
    if performance.event_log:
        # Count products created vs completed
        source_events = [e for e in performance.event_log if e.resource == "Input" and e.activity == "start state"]
        sink_events = [e for e in performance.event_log if e.resource == "Output" and e.activity == "start state"]
        
        print("\nProduct flow:")
        print(f"  Products released by source: {len(source_events)}")
        print(f"  Products completed to sink: {len(sink_events)}")
        print(f"  Products in system (WIP): {len(source_events) - len(sink_events)}")
    
    print("\nCONWIP simulation example completed successfully!")
    print("\nNote: CONWIP control helps stabilize WIP levels and throughput time,")
    print("while potentially reducing throughput compared to uncontrolled release.")


if __name__ == "__main__":
    main()

