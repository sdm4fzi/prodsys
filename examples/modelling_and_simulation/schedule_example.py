"""
Example demonstrating schedule-based production control in prodsys.

This example shows how to:
1. Load a configuration with a predefined schedule
2. Run a simulation with schedule-based product release
3. Analyze how products are released according to the schedule
"""

from prodsys.models import production_system_data
from prodsys.simulation import runner


def main():
    """
    Run a simulation with schedule-based product release.
    
    The schedule defines when specific products should be released into the system.
    The source will use the schedule to determine inter-arrival times and which
    products to create at what time.
    """
    # Load the configuration with schedule
    config = production_system_data.ProductionSystemData.read(
        "examples/modelling_and_simulation/simulation_example_data/schedule_example.json"
    )
    
    print("Configuration loaded successfully!")
    print(f"Number of scheduled events: {len(config.schedule) if config.schedule else 0}")
    
    if config.schedule:
        print("\nSchedule overview:")
        for i, event in enumerate(config.schedule[:5]):  # Show first 5 events
            print(f"  Event {i+1}: Time={event.time}, Product={event.product}, Resource={event.resource}, Process={event.process}")
        if len(config.schedule) > 5:
            print(f"  ... and {len(config.schedule) - 5} more events")
    
    # Create and run the simulation
    print("\nRunning simulation with scheduled product release...")
    sim_runner = runner.Runner(production_system_data=config)
    sim_runner.initialize_simulation()
    sim_runner.run(2000)  # Run for 2000 time units
    
    # Get performance results
    performance = sim_runner.get_performance_data()
    
    print("\nSimulation completed!")
    print(f"Number of events in event log: {len(performance.event_log)}")
    
    # Analyze throughput
    throughput_kpis = [kpi for kpi in performance.kpis if kpi.name.value == "throughput"]
    if throughput_kpis:
        print("\nThroughput KPIs:")
        for kpi in throughput_kpis:
            print(f"  {kpi.product_type if hasattr(kpi, 'product_type') else 'System'}: {kpi.value:.2f}")
    
    # Analyze product releases from schedule
    if performance.event_log:
        scheduled_releases = [
            e for e in performance.event_log 
            if e.activity == "start state" and e.state_type == "Production"
        ]
        print(f"\nNumber of scheduled production starts: {len(scheduled_releases)}")
        
        # Check adherence to schedule
        if config.schedule:
            print("\nSchedule adherence check:")
            for scheduled_event in config.schedule[:3]:
                actual_events = [
                    e for e in scheduled_releases 
                    if e.product == scheduled_event.product and e.resource == scheduled_event.resource
                ]
                if actual_events:
                    actual_time = actual_events[0].time
                    scheduled_time = scheduled_event.time
                    delay = actual_time - scheduled_time
                    print(f"  Product {scheduled_event.product}: Scheduled={scheduled_time:.2f}, Actual={actual_time:.2f}, Delay={delay:.2f}")
    
    print("\nSchedule-based simulation example completed successfully!")


if __name__ == "__main__":
    main()

