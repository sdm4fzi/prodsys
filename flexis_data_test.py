import prodsim
from prodsim.adapters import JsonAdapter, FlexisAdapter
import json

flexis_file_path = "data/adapter_sdm/flexis/Szenario1-84Sek_gut.xlsx"


adapter = FlexisAdapter()

adapter.read_data(flexis_file_path)

from prodsim.util import optimization_util
with open("data/Bosch_scenario.json") as json_file:
    scenario_dict = json.load(json_file)
print(len(adapter.resource_data))
optimization_util.add_machine(adapter, scenario_dict)
print(len(adapter.resource_data))

# JsonAdapter(**adapter.dict()).write_data("data/adapter_sdm/flexis/Szenario1-84Sek_gut.json")

runner_object = prodsim.runner.Runner(adapter=adapter)
runner_object.initialize_simulation()
runner_object.run(3000)
runner_object.save_results_as_csv()
runner_object.print_results()
runner_object.plot_results()
adapter.write_data("data/adapter_sdm/flexis/Szenario1-84Sek_gut_neu.xlsx")
