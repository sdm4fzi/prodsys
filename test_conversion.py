from basyx.aas import model
import basyx.aas.adapter.json.json_serialization
import basyx.aas.adapter.json.json_serialization
import json
from typing import List
import prodsim


from prodsim.new_data_structures import product

example_smc = product.SubmodelElementCollection(ID="012", description="xyz")
example_bom = product.BOM(ID="234", description="hgjkj", assembly="assembly", subProduct=example_smc)
example_product = product.Product(ID="123", description="456", bom=example_bom)



def convert_pydantic_model_to_aas(aas: product.AAS) -> model.AssetAdministrationShell:
    # TODO: transform pydantic model to AAS
      
    # step 1.1: create an identifier for the Asset
    identifier = model.Identifier(
        id_=aas.ID,
        id_type=model.IdentifierType.CUSTOM
    )
    
    # step 1.2: create the Asset object
    asset = model.Asset(
    id_short=aas.ID,
    kind=model.AssetKind.INSTANCE,  
    identification=identifier,     
    )
    
    # ALTERNATIVE: step 2 and 3 can alternatively be done in one step
    submodel = model.Submodel(
    id_short=product.Submodel.ID,
    identification=model.Identifier(product.Submodel.ID, model.IdentifierType.CUSTOM)
    )
    
    submodel = model.Submodel(
    id_short=product.SubmodelElementCollection.ID,
    identification=model.Identifier(product.SubmodelElementCollection.ID, model.IdentifierType.CUSTOM)
    )
    
    aas = model.AssetAdministrationShell(
    id_short=aas.ID,
    identification=model.Identifier(aas.ID, model.IdentifierType.CUSTOM),
    asset=model.AASReference.from_referable(asset),
    submodel={model.AASReference.from_referable(submodel)}
    )
    
    
    
    # step 4.2: create the simple Property
    property_ = model.Property(
    id_short=product.description,  
    value_type=model.datatypes.String, 
    value=string,  
    )

    # step 4.3: add the Property to the Submodel
    submodel.submodel_element.add(property_)
    
    
    pass

basyx_aas = convert_pydantic_model_to_aas(example_product)

aashell_json_string = json.dumps(basyx_aas, cls=basyx.aas.adapter.json.json_serialization.AASToJsonEncoder)
print("\n", aashell_json_string)


def convert_aas_to_pydantic_model(aas: model.AssetAdministrationShell) -> product.AAS:
    # TODO: transform AAS to pydantic model
    pass

new_example_product = convert_aas_to_pydantic_model(basyx_aas)
