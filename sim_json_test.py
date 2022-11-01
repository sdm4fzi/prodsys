from prodsim import loader
import json

simjson_file_path = "data/sim_json_example.json"

with open(simjson_file_path, "r", encoding="utf-8") as json_file:
    simjson_file = json.load(json_file)

    

sim_json = get_default_simjson()

