from flask import Flask, request

from prodsim import env
from prodsim.loader import CustomLoader
from prodsim.optimization_util import get_objective_values
from prodsim.post_processing import PostProcessor

app = Flask(__name__)

@app.route("/", methods=["GET"])
def hello_world():
    env1 = env.Environment()
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

    return l1

@app.route("/test", methods=["GET"])
def dkekd():
    return {"hallo": [1,2, 3]}

