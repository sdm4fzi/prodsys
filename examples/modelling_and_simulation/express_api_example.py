import prodsys.express as psx
import prodsys

tm1 = psx.FunctionTimeModel("normal", 20.0, 5.0)
tm2 = psx.SampleTimeModel([10.0, 20.0, 30.0])
tm3 = psx.DistanceTimeModel(10, 0.2)

bm1 = psx.FunctionTimeModel("exponential", 500.0)
bm2 = psx.SampleTimeModel([10.0, 20.0, 30.0])


p1 = psx.ProductionProcess(tm1)
p2 = psx.CapabilityProcess(tm2, "welding")
p3 = psx.TransportProcess(tm3)


breakdown_state = psx.BreakDownState(bm1, bm2)
process_breakdown_state = psx.ProcessBreakdownState(bm1, bm2, p1)
setup_state = psx.SetupState(tm1, p1, p2)

r1 = psx.Resource(
    [p1, p2],
    [10.0, 10.0],
    capacity=1,
    control_policy="LIFO",
    states=[breakdown_state, process_breakdown_state, setup_state],
)
r2 = psx.Resource([p3], control_policy="FIFO")

m1 = psx.Product([p1, p2], p3)
m2 = psx.Product([p2, p2], p3)

arrival_time_model_m1 = psx.FunctionTimeModel("normal", 140.0, 5.0)
arrival_time_model_m2 = psx.FunctionTimeModel("normal", 160.0, 5.0)

s1 = psx.Source(m1, arrival_time_model_m1, [0.0, 0.0])
s2 = psx.Source(m2, arrival_time_model_m2, [1.0, 0.0])

sk1 = psx.Sink(m1, [20.0, 20.0])
sk2 = psx.Sink(m2, [20.0, 20.0])


ps = psx.ProductionSystem([r1, r2], [s1, s2], [sk1, sk2])

ps.run(7 * 24 * 60)

ps.runner.print_results()

print("Example Results data:\n")
print(ps.post_processor.df_WIP.head())
