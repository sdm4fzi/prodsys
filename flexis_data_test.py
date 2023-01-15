import prodsim
from prodsim.adapters import JsonAdapter, FlexisAdapter
import json

flexis_file_path = "data/adapter_sdm/flexis/Szenario1-84Sek_gut.xlsx"


adapter = FlexisAdapter()

adapter.read_data(flexis_file_path)

# JsonAdapter(**adapter.dict()).write_data("data/adapter_sdm/flexis/Szenario1-84Sek_gut.json")

runner_object = prodsim.runner.Runner(adapter=adapter)
runner_object.initialize_simulation()
runner_object.run(300)
runner_object.save_results_as_csv()
runner_object.print_results()
# runner_object.plot_results()
# loader.write_data("data/Output_data_format/Szenario1-84Sek_gut_neu.json")
