"""
Example: Using the interval-based AnalyticsStore for simulation analysis.

Demonstrates:
  - Running a simulation and accessing the AnalyticsStore
  - Querying throughput, resource states, OEE, WIP, scrap, flow ratio
  - Interval queries (KPIs over arbitrary time windows)
  - Incremental event append
  - Warm-up detection as a query parameter
"""

import prodsys
import prodsys.express as psx
from prodsys.analytics import AnalyticsStore, detect_warm_up

prodsys.set_logging("WARNING")
print("prodsys version:", prodsys.VERSION)

# ── Build a production system ────────────────────────────────────────────

t1 = psx.FunctionTimeModel("normal", 1, 0.1, "t1")
t2 = psx.FunctionTimeModel("normal", 2, 0.2, "t2")
p1 = psx.ProductionProcess(t1, "p1")
p2 = psx.ProductionProcess(t2, "p2")
t3 = psx.DistanceTimeModel(speed=180, reaction_time=0.1, ID="t3")
tp = psx.TransportProcess(t3, "tp")

s1 = psx.FunctionTimeModel("exponential", 0.5, ID="s1")
setup1 = psx.SetupState(s1, p1, p2, "S1")
setup2 = psx.SetupState(s1, p2, p1, "S2")

machine = psx.Resource([p1, p2], [5, 0], 2, states=[setup1, setup2], ID="machine")
machine2 = psx.Resource([p1, p2], [7, 0], 2, states=[setup1, setup2], ID="machine2")
transport = psx.Resource([tp], [2, 0], 1, ID="transport")

product1 = psx.Product([p1, p2], tp, "product1")
product2 = psx.Product([p2, p1], tp, "product2")

sink1 = psx.Sink(product1, [10, 0], "sink1")
sink2 = psx.Sink(product2, [10, 0], "sink2")

arrival1 = psx.FunctionTimeModel("exponential", 1, ID="arrival1")
arrival2 = psx.FunctionTimeModel("exponential", 2, ID="arrival2")
source1 = psx.Source(product1, arrival1, [0, 0], ID="source_1")
source2 = psx.Source(product2, arrival2, [0, 0], ID="source_2")

system = psx.ProductionSystem([machine, machine2, transport], [source1, source2], [sink1, sink2])
model = system.to_model()

# ── Run simulation ───────────────────────────────────────────────────────

runner = prodsys.runner.Runner(production_system_data=model)
runner.initialize_simulation()
system.run(1000)
runner = system.runner

# ── Access the AnalyticsStore via PostProcessor ──────────────────────────

pp = runner.get_post_processor()
store = pp.store

print("\n" + "=" * 60)
print("  ANALYTICS STORE — Interval-Based KPI Pipeline")
print("=" * 60)

# ── 1. Throughput ────────────────────────────────────────────────────────

print("\n─── Throughput (per finished product) ───")
df_tp = store.throughput()
print(f"  Total finished products: {len(df_tp)}")
print(f"  Product types: {df_tp['Product_type'].unique().tolist()}")

print("\n─── Aggregated throughput time (mean per product type) ───")
print(store.aggregated_throughput_time())

print("\n─── Output and throughput rate ───")
print(store.aggregated_output_and_throughput())

# ── 2. Resource states ───────────────────────────────────────────────────

print("\n─── Resource states (full simulation) ───")
rs = store.resource_states()
print(rs.set_index(["Resource", "Time_type"])[["time_increment", "percentage"]])

# ── 3. Interval query: resource states for a specific time window ────────

print("\n─── Resource states for t=[200, 800] only ───")
rs_window = store.resource_states(t_from=200, t_to=800)
if len(rs_window) > 0:
    print(rs_window.set_index(["Resource", "Time_type"])[["time_increment", "percentage"]])

# ── 4. Resource states over time (bucketed) ──────────────────────────────

print("\n─── Resource states by 100-minute intervals (first 3 intervals) ───")
rs_by_interval = store.resource_states_by_interval(100.0)
if len(rs_by_interval) > 0:
    sample = rs_by_interval[rs_by_interval["Interval_start"] < 300]
    print(sample.to_string(index=False))

# ── 5. OEE ───────────────────────────────────────────────────────────────

print("\n─── OEE per resource ───")
oee = store.oee_per_resource()
if len(oee) > 0:
    print(oee.set_index("Resource"))

print("\n─── System OEE ───")
print(store.oee_production_system().set_index("KPI"))

# ── 6. WIP ───────────────────────────────────────────────────────────────

print("\n─── Aggregated WIP (mean per product type) ───")
print(store.aggregated_wip())

# ── 7. Scrap ─────────────────────────────────────────────────────────────

print("\n─── Scrap per product type ───")
scrap = store.scrap_per_product_type()
if len(scrap) > 0:
    print(scrap.set_index("Product_type"))
else:
    print("  No scrap (all processes succeeded)")

# ── 8. Production flow ratio ────────────────────────────────────────────

print("\n─── Production flow ratio ───")
flow = store.production_flow_ratio()
if len(flow) > 0:
    print(flow.set_index("Product_type"))

# ── 9. Warm-up detection as a query parameter ───────────────────────────

print("\n─── Warm-up detection ───")
cutoff = detect_warm_up(store, method="static_ratio")
print(f"  Warm-up cutoff time (static_ratio): {cutoff:.1f}")
print(f"  Aggregated throughput time (post warm-up):")
print(store.aggregated_throughput_time(t_from=cutoff))

# ── 10. Direct interval access ──────────────────────────────────────────

print("\n─── Raw intervals (first 5 resource intervals) ───")
ri = store.resource_intervals()
print(ri[["entity_id", "state_type", "t_start", "t_end", "duration", "product_id"]].head(5).to_string(index=False))

print("\n─── Product lifecycle intervals (first 5) ───")
pi = store.product_intervals()
in_sys = pi[pi["state_type"] == "in_system"]
print(in_sys[["product_id", "product_type", "t_start", "t_end", "duration"]].head(5).to_string(index=False))

# ── 11. Incremental append ───────────────────────────────────────────────

print("\n─── Incremental append demo ───")
store2 = AnalyticsStore(time_range=1000, production_system_data=model)
df_raw = pp.df_raw
mid = len(df_raw) // 2
store2.ingest_events(df_raw.iloc[:mid])
store2.ingest_events(df_raw.iloc[mid:])
print(f"  Full ingest output: {store.aggregated_output().sum()}")
print(f"  Incremental output: {store2.aggregated_output().sum()}")
print(f"  Match: {store.aggregated_output().sum() == store2.aggregated_output().sum()}")

# ── 12. print_results uses the new analytics ─────────────────────────────

print("\n" + "=" * 60)
print("  runner.print_results() — powered by AnalyticsStore")
print("=" * 60)
runner.print_results()
