from basyx.aas import model
import basyx.aas.adapter.json.json_serialization
import basyx.aas.adapter.json.json_serialization
import json
from typing import List
import prodsim


from prodsim.new_data_structures import product

example_smc = product.SubmodelElementCollection()
example_bom = product.BOM(ID="234", description="hgjkj", assembly="assembly", subProduct=example_smc)
example_product = product.Product(ID="123", description="456", bom=example_bom)



def convert_pydantic_model_to_aas(aas: product.AAS) -> model.AssetAdministrationShell:
    # TODO: transform pydantic model to AAS
    pass

basyx_aas = convert_pydantic_model_to_aas(example_product)
aashell_json_string = json.dumps(basyx_aas, cls=basyx.aas.adapter.json.json_serialization.AASToJsonEncoder)
print("\n", aashell_json_string)


def convert_aas_to_pydantic_model(aas: model.AssetAdministrationShell) -> product.AAS:
    # TODO: transform pydantic model to AAS
    pass

new_example_product = convert_aas_to_pydantic_model(basyx_aas)
