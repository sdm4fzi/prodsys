import prodsim
from prodsim.adapters import JsonAdapter, FlexisAdapter
import json

flexis_file_path = "data/adapter_sdm/flexis/Szenario1-84Sek_gut.xlsx"


adapter = FlexisAdapter()

adapter.read_data(flexis_file_path)

copy = adapter.copy(deep=True)
copy.resource_data.remove(copy.resource_data[0])


print(len(adapter.resource_data))
print(len(copy.resource_data))