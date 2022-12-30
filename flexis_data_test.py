from prodsim.adapters.flexis_adapter import FlexisAdapter
import prodsim
import json

flexis_file_path = "data/adapter_sdm/flexis/Szenario1-84Sek_gut.xlsx"

# with open(simjson_file_path, "r", encoding="utf-8") as json_file:
#     simjson_file = json.load(json_file)

adapter = FlexisAdapter()

adapter.read_data(flexis_file_path)

runner_object = prodsim.runner.Runner(adapter=adapter)
runner_object.initialize_simulation()
runner_object.run(3000)
runner_object.save_results_as_csv()
runner_object.print_results()
runner_object.plot_results()
# loader.write_data("data/Output_data_format/Szenario1-84Sek_gut_neu.json")

