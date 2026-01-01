import prodsys.express as psx
import prodsys

print("version used:", prodsys.VERSION)
prodsys.set_logging("CRITICAL")

# Create time models
t1 = psx.FunctionTimeModel("normal", 1, 0.1, "t1")
t2 = psx.FunctionTimeModel("normal", 2, 0.2, "t2")

# Create processes
p1 = psx.ProductionProcess(t1, "p1")
p2 = psx.ProductionProcess(t2, "p2")

t3 = psx.DistanceTimeModel(speed=180, reaction_time=0.1, ID="t3")
tp = psx.TransportProcess(t3, "tp")

# Create setup states
s1 = psx.FunctionTimeModel("exponential", 0.5, ID="s1")
setup_state_1 = psx.SetupState(s1, p1, p2, "S1")
setup_state_2 = psx.SetupState(s1, p2, p1, "S2")

# Create resources
machine = psx.Resource(
    [p1, p2],
    [5, 0],
    2,
    states=[setup_state_1, setup_state_2],
    ID="machine",
)
machine2 = psx.Resource(
    [p1, p2],
    [7, 0],
    2,
    states=[setup_state_1, setup_state_2],
    ID="machine2",
)

transport = psx.Resource([tp], [2, 0], 1, ID="transport")

# Create products
product1 = psx.Product([p1, p2], tp, "product1")
product2 = psx.Product([p2, p1], tp, "product2")

# Create sinks
sink1 = psx.Sink(product1, [10, 0], "sink1")
sink2 = psx.Sink(product2, [10, 0], "sink2")

# Create orders with different release times
order1 = psx.Order(
    ID="order1",
    ordered_products=[psx.OrderedProduct(product=product1, quantity=2)],
    order_time=0.0,
    release_time=10.0,
    priority=1,
)

order2 = psx.Order(
    ID="order2",
    ordered_products=[psx.OrderedProduct(product=product2, quantity=1)],
    order_time=5.0,
    release_time=15.0,
    priority=1,
)

# Order with multiple product types
order3 = psx.Order(
    ID="order3",
    ordered_products=[
        psx.OrderedProduct(product=product1, quantity=1),
        psx.OrderedProduct(product=product2, quantity=1),
    ],
    order_time=10.0,
    release_time=20.0,
    priority=1,
)

# Create order source
order_source = psx.OrderSource(
    orders=[order1, order2, order3],
    location=[0, 0],
    ID="order_source",
)

# Create production system
system = psx.ProductionSystem(
    [machine, machine2, transport], [order_source], [sink1, sink2]
)

# Set ConWip limit
model = system.to_model()
model.conwip_number = 5

# Run simulation
runner_instance = prodsys.runner.Runner(production_system_data=model)
runner_instance.initialize_simulation()
system.run(100)

runner_instance = system.runner

runner_instance.print_results()
runner_instance.plot_results()
runner_instance.save_results_as_csv()

