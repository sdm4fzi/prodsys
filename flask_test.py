from flask import Flask, request

from prodsim import sim
from prodsim.loader import CustomLoader
from prodsim.optimization_util import get_objective_values
from prodsim.post_processing import PostProcessor

app = Flask(__name__)

@app.route("/simulate", methods=["GET"])
def home():
    env1 = sim.Environment()
    loader = CustomLoader()
    data = request.json
    loader.set_values(data)
    env1.loader = loader

    env1.initialize_simulation()

    import time

    t_0 = time.perf_counter()

    env1.run(2000)

    t_1 = time.perf_counter()

    df = env1.data_collector.get_data()
    p = PostProcessor(df_raw=df)
    l1 = get_objective_values(env1, p)
    l1 = [float(value) for value in l1]
    results = {
            'throughput': l1[0],
            'wip': l1[1],
            'throughput_time': l1[2],
            'cost': l1[3]
        }
    return results

@app.route("/test", methods=["GET"])
def test():
    return {"hallo": [1,2, 3]}

