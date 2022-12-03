from prodsim import loader
from prodsim.flexis_adapter import FlexisAdapter
import json

flexis_file_path = "data/Output_data_format/Szenario1-84Sek_gut.xlsx"

# with open(simjson_file_path, "r", encoding="utf-8") as json_file:
#     simjson_file = json.load(json_file)

loader = FlexisAdapter()

loader.read_data(flexis_file_path)
    

loader.write_data("data/Output_data_format/Szenario1-84Sek_gut_neu.json")

