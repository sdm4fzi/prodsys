# import json

# with open('data/Bosch_scenario.json') as f:
#     data = json.load(f)

# print(data)

# from prodsim.data_structures import scenario_data

# scenario = scenario_data.ScenarioData(**data)

# print(scenario)

import prodsim

adapter = prodsim.adapters.JsonAdapter()
adapter.read_data("data/base_scenario.json", 'data/Bosch_scenario.json')
print(adapter)