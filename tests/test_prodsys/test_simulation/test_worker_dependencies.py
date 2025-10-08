import pytest
from prodsys.models.production_system_data import ProductionSystemData
import prodsys.express as psx
from prodsys import runner


@pytest.fixture
def simulation_adapter_process_dependency() -> ProductionSystemData:
    """Test system with process dependency (assembly dependency)"""
    t1 = psx.FunctionTimeModel("normal", 1, 0.1, "t1")
    t2 = psx.FunctionTimeModel("normal", 2, 0.2, "t2")

    p1 = psx.ProductionProcess(t1, "p1")
    p2 = psx.ProductionProcess(t2, "p2")

    t3 = psx.DistanceTimeModel(speed=180, reaction_time=0.1, ID="t3")

    tp = psx.TransportProcess(t3, "tp")
    move_p = psx.TransportProcess(t3, "move")

    s1 = psx.FunctionTimeModel("exponential", 0.5, ID="s1")
    setup_state_1 = psx.SetupState(s1, p1, p2, "S1")
    setup_state_2 = psx.SetupState(s1, p2, p1, "S2")

    assembly_process = psx.ProductionProcess(
        psx.FunctionTimeModel("exponential", 0.1, ID="fake_process"), "fake_process"
    )

    worker = psx.Resource(
        [move_p, assembly_process],
        [2, 0],
        1,
        ID="worker",
    )

    interaction_node_assembly = psx.Node(location=[5, 6], ID="interaction_node_assembly")

    assembly_dependency = psx.ProcessDependency(
        ID="assembly_dependency",
        required_process=assembly_process,
        interaction_node=interaction_node_assembly,
    )

    machine = psx.Resource(
        [p1, p2],
        [5, 5],
        1,
        states=[setup_state_1, setup_state_2],
        ID="machine",
        dependencies=[assembly_dependency],
    )

    transport = psx.Resource([tp], [2, 2], 1, ID="transport")

    product1 = psx.Product([p1], tp, "product1")
    product2 = psx.Product([p2], tp, "product2")

    sink1 = psx.Sink(product1, [10, 0], "sink1")
    sink2 = psx.Sink(product2, [10, 0], "sink2")

    arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")
    arrival_model_2 = psx.FunctionTimeModel("exponential", 2, ID="arrival_model_2")

    source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")
    source2 = psx.Source(product2, arrival_model_2, [0, 0], ID="source_2")

    system = psx.ProductionSystem(
        [machine, transport, worker],
        [source1, source2],
        [sink1, sink2],
    )
    adapter = system.to_model()
    return adapter


@pytest.fixture
def simulation_adapter_resource_dependency() -> ProductionSystemData:
    """Test system with resource dependency"""
    t1 = psx.FunctionTimeModel("normal", 1, 0.1, "t1")
    t2 = psx.FunctionTimeModel("normal", 2, 0.2, "t2")

    p1 = psx.ProductionProcess(t1, "p1")
    p2 = psx.ProductionProcess(t2, "p2")

    t3 = psx.DistanceTimeModel(speed=180, reaction_time=0.1, ID="t3")

    tp = psx.TransportProcess(t3, "tp")
    move_p = psx.TransportProcess(t3, "move")

    s1 = psx.FunctionTimeModel("exponential", 0.5, ID="s1")
    setup_state_1 = psx.SetupState(s1, p1, p2, "S1")
    setup_state_2 = psx.SetupState(s1, p2, p1, "S2")

    assembly_process = psx.ProductionProcess(
        psx.FunctionTimeModel("exponential", 0.1, ID="fake_process"), "fake_process"
    )

    worker2 = psx.Resource(
        [move_p, assembly_process],
        [3, 0],
        1,
        ID="worker2",
    )

    interaction_node_resource = psx.Node(location=[7, 4], ID="interaction_node_resource")

    resource_dependency = psx.ResourceDependency(
        ID="resource_dependency",
        required_resource=worker2,
        interaction_node=interaction_node_resource,
    )

    machine2 = psx.Resource(
        [p1, p2],
        [7, 2],
        2,
        states=[setup_state_1, setup_state_2],
        ID="machine2",
        dependencies=[resource_dependency],
    )

    transport = psx.Resource([tp], [2, 2], 1, ID="transport")

    product1 = psx.Product([p1], tp, "product1")
    product2 = psx.Product([p2], tp, "product2")

    sink1 = psx.Sink(product1, [10, 0], "sink1")
    sink2 = psx.Sink(product2, [10, 0], "sink2")

    arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")
    arrival_model_2 = psx.FunctionTimeModel("exponential", 2, ID="arrival_model_2")

    source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")
    source2 = psx.Source(product2, arrival_model_2, [0, 0], ID="source_2")

    system = psx.ProductionSystem(
        [machine2, transport, worker2],
        [source1, source2],
        [sink1, sink2],
    )
    adapter = system.to_model()
    return adapter


@pytest.fixture
def simulation_adapter_both_dependencies() -> ProductionSystemData:
    """Test system with both process and resource dependencies"""
    t1 = psx.FunctionTimeModel("normal", 1, 0.1, "t1")
    t2 = psx.FunctionTimeModel("normal", 2, 0.2, "t2")

    p1 = psx.ProductionProcess(t1, "p1")
    p2 = psx.ProductionProcess(t2, "p2")

    t3 = psx.DistanceTimeModel(speed=180, reaction_time=0.1, ID="t3")

    tp = psx.TransportProcess(t3, "tp")
    move_p = psx.TransportProcess(t3, "move")

    s1 = psx.FunctionTimeModel("exponential", 0.5, ID="s1")
    setup_state_1 = psx.SetupState(s1, p1, p2, "S1")
    setup_state_2 = psx.SetupState(s1, p2, p1, "S2")

    assembly_process = psx.ProductionProcess(
        psx.FunctionTimeModel("exponential", 0.1, ID="fake_process"), "fake_process"
    )

    worker = psx.Resource(
        [move_p, assembly_process],
        [2, 0],
        1,
        ID="worker",
    )

    worker2 = psx.Resource(
        [move_p, assembly_process],
        [3, 0],
        1,
        ID="worker2",
    )

    interaction_node_assembly = psx.Node(location=[5, 6], ID="interaction_node_assembly")
    interaction_node_resource_2 = psx.Node(location=[7, 4], ID="interaction_node_resource_2")

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
        2,
        states=[setup_state_1, setup_state_2],
        ID="machine2",
        dependencies=[resource_2_dependency],
    )

    transport = psx.Resource([tp], [2, 2], 1, ID="transport")

    product1 = psx.Product([p1], tp, "product1")
    product2 = psx.Product([p2], tp, "product2")

    sink1 = psx.Sink(product1, [10, 0], "sink1")
    sink2 = psx.Sink(product2, [10, 0], "sink2")

    arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")
    arrival_model_2 = psx.FunctionTimeModel("exponential", 2, ID="arrival_model_2")

    source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")
    source2 = psx.Source(product2, arrival_model_2, [0, 0], ID="source_2")

    system = psx.ProductionSystem(
        [machine, machine2, transport, worker, worker2],
        [source1, source2],
        [sink1, sink2],
    )
    adapter = system.to_model()
    return adapter


def test_initialize_simulation_process_dependency(
    simulation_adapter_process_dependency: ProductionSystemData,
):
    runner_instance = runner.Runner(
        production_system_data=simulation_adapter_process_dependency
    )
    runner_instance.initialize_simulation()


def test_initialize_simulation_resource_dependency(
    simulation_adapter_resource_dependency: ProductionSystemData,
):
    runner_instance = runner.Runner(
        production_system_data=simulation_adapter_resource_dependency
    )
    runner_instance.initialize_simulation()


def test_initialize_simulation_both_dependencies(
    simulation_adapter_both_dependencies: ProductionSystemData,
):
    runner_instance = runner.Runner(
        production_system_data=simulation_adapter_both_dependencies
    )
    runner_instance.initialize_simulation()


def test_hashing_process_dependency(
    simulation_adapter_process_dependency: ProductionSystemData,
):
    hash_str = simulation_adapter_process_dependency.hash()
    assert hash_str == "90b05fbe4291fde09227d06934a731fc"


def test_hashing_resource_dependency(
    simulation_adapter_resource_dependency: ProductionSystemData,
):
    hash_str = simulation_adapter_resource_dependency.hash()
    assert hash_str == "02b202eab366c2ec634e9030d30c2c50"


def test_hashing_both_dependencies(
    simulation_adapter_both_dependencies: ProductionSystemData,
):
    hash_str = simulation_adapter_both_dependencies.hash()
    assert hash_str == "0548f963430e9fc11b13aa0c23afaa05"


def test_run_simulation_process_dependency(
    simulation_adapter_process_dependency: ProductionSystemData,
):
    runner_instance = runner.Runner(
        production_system_data=simulation_adapter_process_dependency
    )
    runner_instance.initialize_simulation()
    runner_instance.run(1000)
    assert runner_instance.env.now == 1000
    post_processor = runner_instance.get_post_processor()

    # Check output KPIs
    product1_output = 0
    product2_output = 0
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output" and kpi.product_type == "product1":
            product1_output = kpi.value
            assert kpi.value > 250 and kpi.value < 400
        if kpi.name == "output" and kpi.product_type == "product2":
            product2_output = kpi.value
            assert kpi.value > 100 and kpi.value < 170

    # Verify outputs are reasonable
    assert product1_output > 0
    assert product2_output > 0

    # Check machine state KPIs - worker should have dependency process time
    worker_pr_found = False
    machine_pr_found = False
    for kpi in post_processor.machine_state_KPIS:
        if kpi.name == "productive_time" and kpi.resource == "worker":
            worker_pr_found = True
            # Worker should have some productive time from the assembly process
            assert kpi.value > 0 and kpi.value < 100
        if kpi.name == "productive_time" and kpi.resource == "machine":
            machine_pr_found = True
            assert kpi.value > 40 and kpi.value < 80

    assert worker_pr_found, "Worker productive time KPI not found"
    assert machine_pr_found, "Machine productive time KPI not found"

    # Check WIP KPIs
    total_wip = 0
    for kpi in post_processor.WIP_KPIs:
        if kpi.name == "WIP":
            total_wip += kpi.value
            assert kpi.value > 0

    assert total_wip > 800 and total_wip < 1200


def test_run_simulation_resource_dependency(
    simulation_adapter_resource_dependency: ProductionSystemData,
):
    runner_instance = runner.Runner(
        production_system_data=simulation_adapter_resource_dependency
    )
    runner_instance.initialize_simulation()
    runner_instance.run(1000)
    assert runner_instance.env.now == 1000
    post_processor = runner_instance.get_post_processor()

    # Check output KPIs
    product1_output = 0
    product2_output = 0
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output" and kpi.product_type == "product1":
            product1_output = kpi.value
            assert kpi.value > 350 and kpi.value < 550
        if kpi.name == "output" and kpi.product_type == "product2":
            product2_output = kpi.value
            assert kpi.value > 150 and kpi.value < 300

    # Verify outputs are reasonable
    assert product1_output > 0
    assert product2_output > 0

    # Check machine state KPIs - worker2 should have dependency time
    worker2_pr_found = False
    worker2_dp_found = False
    machine2_pr_found = False
    for kpi in post_processor.machine_state_KPIS:
        if kpi.name == "productive_time" and kpi.resource == "worker2":
            worker2_pr_found = True
            assert kpi.value >= 0 and kpi.value < 1
        if kpi.name == "dependency_time" and kpi.resource == "worker2":
            worker2_dp_found = True
            # Worker2 should have significant dependency time (almost 100%)
            assert kpi.value > 95 and kpi.value <= 100
        if kpi.name == "productive_time" and kpi.resource == "machine2":
            machine2_pr_found = True
            assert kpi.value > 75 and kpi.value < 90

    assert worker2_pr_found, "Worker2 productive time KPI not found"
    assert worker2_dp_found, "Worker2 dependency time KPI not found"
    assert machine2_pr_found, "Machine2 productive time KPI not found"

    # Check WIP KPIs
    total_wip = 0
    for kpi in post_processor.WIP_KPIs:
        if kpi.name == "WIP":
            total_wip += kpi.value
            assert kpi.value > 0

    assert total_wip > 600 and total_wip < 1000


def test_run_simulation_both_dependencies(
    simulation_adapter_both_dependencies: ProductionSystemData,
):
    runner_instance = runner.Runner(
        production_system_data=simulation_adapter_both_dependencies
    )
    runner_instance.initialize_simulation()
    runner_instance.run(1000)
    assert runner_instance.env.now == 1000
    post_processor = runner_instance.get_post_processor()

    # Check output KPIs
    product1_output = 0
    product2_output = 0
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output" and kpi.product_type == "product1":
            product1_output = kpi.value
            assert kpi.value > 500 and kpi.value < 600
        if kpi.name == "output" and kpi.product_type == "product2":
            product2_output = kpi.value
            assert kpi.value > 200 and kpi.value < 300

    # Verify outputs are reasonable
    assert product1_output > 0
    assert product2_output > 0

    # Check machine state KPIs for both workers
    worker_pr_found = False
    worker2_dp_found = False
    machine_pr_found = False
    machine2_pr_found = False

    for kpi in post_processor.machine_state_KPIS:
        if kpi.name == "productive_time" and kpi.resource == "worker":
            worker_pr_found = True
            # Worker should have some productive time from the assembly process
            assert kpi.value > 0 and kpi.value < 100
        if kpi.name == "dependency_time" and kpi.resource == "worker2":
            worker2_dp_found = True
            # Worker2 should have significant dependency time
            assert kpi.value > 95 and kpi.value <= 100
        if kpi.name == "productive_time" and kpi.resource == "machine":
            machine_pr_found = True
            assert kpi.value > 35 and kpi.value < 50
        if kpi.name == "productive_time" and kpi.resource == "machine2":
            machine2_pr_found = True
            assert kpi.value > 60 and kpi.value < 70

    assert worker_pr_found, "Worker productive time KPI not found"
    assert worker2_dp_found, "Worker2 dependency time KPI not found"
    assert machine_pr_found, "Machine productive time KPI not found"
    assert machine2_pr_found, "Machine2 productive time KPI not found"

    # Check WIP KPIs
    total_wip = 0
    for kpi in post_processor.WIP_KPIs:
        if kpi.name == "WIP":
            total_wip += kpi.value
            assert kpi.value > 0

    assert total_wip > 650 and total_wip < 750

    # Check throughput time
    for kpi in post_processor.aggregated_throughput_time_KPIs:
        if kpi.name == "throughput_time":
            assert kpi.value > 200 and kpi.value < 250

