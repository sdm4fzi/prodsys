"""
Example demonstrating schedule-based production control in prodsys using OrderSource.

This example shows how to:
1. Load a configuration with OrderSource and orders matching a schedule
2. Run a simulation with schedule-based product release via orders
3. Analyze how products are released according to the schedule
4. Validate routing when multiple resources can perform the same process

Note: This example uses OrderSource with orders that match the schedule. The schedule controls:
- Product IDs: Products are created with IDs from the schedule
- Release timing: Orders are released at scheduled times
- Routing: Products are routed to specific resources as specified in the schedule
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
    
    if config.order_data:
        print(f"\nNumber of orders: {len(config.order_data)}")
        for order in config.order_data:
            print(f"  Order {order.ID}: Release time={order.release_time or order.order_time}, Products={[op.product_type for op in order.ordered_products]}")
    
    if config.schedule:
        print("\nSchedule overview:")
        print(f"  Total scheduled events: {len(config.schedule)}")
        unique_products = set()
        for event in config.schedule:
            # Extract product ID (e.g., "Product_A_1" -> "Product_A_1")
            product_id = event.product
            if "_" in product_id:
                product_base = "_".join(product_id.split("_")[:-1])
                unique_products.add(product_base)
        print(f"  Unique products in schedule: {len(unique_products)}")
        if len(config.schedule) <= 10:
            for i, event in enumerate(config.schedule):
                print(f"  Event {i+1}: Time={event.time}, Product={event.product}, Resource={event.resource}, Process={event.process}")
        else:
            print("  First 5 events:")
            for i, event in enumerate(config.schedule[:5]):
                print(f"  Event {i+1}: Time={event.time}, Product={event.product}, Resource={event.resource}, Process={event.process}")
            print(f"  ... and {len(config.schedule) - 5} more events")
    
    # Create and run the simulation
    print("\nRunning simulation with scheduled product release...")
    print("Note: Only products specified in the schedule will be released.")
    sim_runner = runner.Runner(production_system_data=config)
    sim_runner.initialize_simulation()
    
    # Calculate a reasonable simulation time based on schedule
    if config.schedule:
        max_schedule_time = max(event.time for event in config.schedule)
        # Add buffer for processing time (assume max 50 time units for any process)
        simulation_time = max_schedule_time + 100
    else:
        simulation_time = 2000
    
    sim_runner.run(simulation_time)
    
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
        
        # Debug: Show all product IDs in event log
        if config.schedule:
            all_product_ids = set(e.product for e in scheduled_releases)
            scheduled_product_ids = set(e.product for e in config.schedule)
            print("\nDebug info:")
            print(f"  Scheduled product IDs: {sorted(scheduled_product_ids)}")
            print(f"  Actual product IDs in event log: {sorted(list(all_product_ids))}")
            missing = sorted(scheduled_product_ids - all_product_ids)
            if missing:
                print(f"  Missing from event log: {missing}")
            else:
                print("  All scheduled products found in event log")
            extra = sorted(all_product_ids - scheduled_product_ids)
            if extra:
                print(f"  WARNING: Extra products found (not in schedule): {extra[:10]}")
                print("  Note: This may indicate that sources continued creating products after schedule was exhausted.")
            else:
                print("  ✓ No extra products released (only scheduled products)")
        
        # Check adherence to schedule and routing
        if config.schedule:
            print("\nSchedule adherence and routing validation:")
            routing_correct = True
            routing_mismatches = []
            missing_products = []
            
            for scheduled_event in config.schedule:
                # Match by product_id AND process/state (since products with multiple processes
                # appear multiple times in the schedule with the same product_id)
                scheduled_process = scheduled_event.process
                actual_events = [
                    e for e in scheduled_releases 
                    if e.product == scheduled_event.product
                    and hasattr(e, 'state') and e.state == scheduled_process
                ]
                
                # If no exact match, try to find by product type and process
                if not actual_events:
                    product_type = scheduled_event.product.split("_")[0]
                    process_id = scheduled_event.process
                    actual_events = [
                        e for e in scheduled_releases 
                        if e.product.startswith(product_type + "_") 
                        and hasattr(e, 'state') and e.state == process_id
                    ]
                    # Sort by time to get the first matching one
                    actual_events.sort(key=lambda x: x.time)
                
                if actual_events:
                    actual_event = actual_events[0]
                    actual_time = actual_event.time
                    scheduled_time = scheduled_event.time
                    delay = actual_time - scheduled_time
                    scheduled_resource = scheduled_event.resource
                    actual_resource = actual_event.resource
                    
                    # Validate routing
                    resource_match = actual_resource == scheduled_resource
                    if not resource_match:
                        routing_correct = False
                        routing_mismatches.append({
                            'product': scheduled_event.product,
                            'scheduled': scheduled_resource,
                            'actual': actual_resource
                        })
                    
                    status = "✓" if resource_match else "✗"
                    match_info = f" (matched {actual_event.product})" if actual_event.product != scheduled_event.product else ""
                    print(f"  {status} Product {scheduled_event.product}{match_info}: "
                          f"Scheduled={scheduled_time:.2f} @ {scheduled_resource}, "
                          f"Actual={actual_time:.2f} @ {actual_resource}, "
                          f"Delay={delay:.2f}")
                else:
                    print(f"  ✗ Product {scheduled_event.product}: Not found in event log")
                    missing_products.append(scheduled_event.product)
                    routing_correct = False
            
            # Summary of routing validation
            print("\nRouting validation summary:")
            if routing_correct and not missing_products:
                print("  ✓ All products were routed to the correct resources as specified in the schedule")
            else:
                if missing_products:
                    print(f"  ✗ {len(missing_products)} products from schedule were not found in event log")
                if routing_mismatches:
                    print(f"  ✗ {len(routing_mismatches)} products were routed to wrong resources:")
                    for mm in routing_mismatches[:5]:  # Show first 5
                        print(f"    - {mm['product']}: scheduled {mm['scheduled']}, got {mm['actual']}")
            
            # Count processes by resource
            p1_events = [
                e for e in scheduled_releases 
                if hasattr(e, 'state') and e.state == "P1"
            ]
            p2_events = [
                e for e in scheduled_releases 
                if hasattr(e, 'state') and e.state == "P2"
            ]
            
            if p1_events:
                print("\nP1 process distribution:")
                r1_count = sum(1 for e in p1_events if e.resource == "R1")
                r4_count = sum(1 for e in p1_events if e.resource == "R4")
                r5_count = sum(1 for e in p1_events if e.resource == "R5")
                print(f"  R1: {r1_count} processes")
                print(f"  R4: {r4_count} processes")
                print(f"  R5: {r5_count} processes")
                print(f"  Total P1 processes: {len(p1_events)}")
                
                # Show schedule expectations
                p1_scheduled = [e for e in config.schedule if e.process == "P1"]
                print("\nSchedule expectations for P1:")
                r1_scheduled = sum(1 for e in p1_scheduled if e.resource == "R1")
                r4_scheduled = sum(1 for e in p1_scheduled if e.resource == "R4")
                r5_scheduled = sum(1 for e in p1_scheduled if e.resource == "R5")
                print(f"  R1: {r1_scheduled} scheduled")
                print(f"  R4: {r4_scheduled} scheduled")
                print(f"  R5: {r5_scheduled} scheduled")
                print(f"  Total scheduled P1: {len(p1_scheduled)}")
            
            if p2_events:
                print("\nP2 process distribution:")
                r2_count = sum(1 for e in p2_events if e.resource == "R2")
                r3_count = sum(1 for e in p2_events if e.resource == "R3")
                r6_count = sum(1 for e in p2_events if e.resource == "R6")
                r7_count = sum(1 for e in p2_events if e.resource == "R7")
                print(f"  R2: {r2_count} processes")
                print(f"  R3: {r3_count} processes")
                print(f"  R6: {r6_count} processes")
                print(f"  R7: {r7_count} processes")
                print(f"  Total P2 processes: {len(p2_events)}")
                
                # Show schedule expectations
                p2_scheduled = [e for e in config.schedule if e.process == "P2"]
                print("\nSchedule expectations for P2:")
                r2_scheduled = sum(1 for e in p2_scheduled if e.resource == "R2")
                r3_scheduled = sum(1 for e in p2_scheduled if e.resource == "R3")
                r6_scheduled = sum(1 for e in p2_scheduled if e.resource == "R6")
                r7_scheduled = sum(1 for e in p2_scheduled if e.resource == "R7")
                print(f"  R2: {r2_scheduled} scheduled")
                print(f"  R3: {r3_scheduled} scheduled")
                print(f"  R6: {r6_scheduled} scheduled")
                print(f"  R7: {r7_scheduled} scheduled")
                print(f"  Total scheduled P2: {len(p2_scheduled)}")
            
            # Count products by type
            print("\nProduct type distribution:")
            product_a_count = sum(1 for e in scheduled_releases if e.product.startswith("Product_A_"))
            product_b_count = sum(1 for e in scheduled_releases if e.product.startswith("Product_B_"))
            product_c_count = sum(1 for e in scheduled_releases if e.product.startswith("Product_C_"))
            print(f"  Product_A: {product_a_count} production starts")
            print(f"  Product_B: {product_b_count} production starts")
            print(f"  Product_C: {product_c_count} production starts")
            
            # Count unique products
            unique_products = set(e.product.split("_")[0] + "_" + e.product.split("_")[1] for e in scheduled_releases)
            print(f"  Unique products: {len(unique_products)}")
    
    print("\nSchedule-based simulation example completed successfully!")


if __name__ == "__main__":
    main()

