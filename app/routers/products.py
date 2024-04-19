from typing import List, Annotated


from fastapi import APIRouter, HTTPException, Body
from sympy import Product


import prodsys
from prodsys.models import (
    product_data,
)
from app.dependencies import prodsys_backend, get_product_from_backend

PRODUCT_LIST_EXAMPLE = product_data.ProductData.Config.schema_extra["examples"]

router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/products",
    tags=["products"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/",
    response_model=List[product_data.ProductData],
    responses={
        200: {
            "description": "Sucessfully returned product data",
            "content": {
                "application/json": {
                    "example": PRODUCT_LIST_EXAMPLE
                }
            }
        },
        404: {"description": "No product data found."}
    }
)
async def get_products(project_id: str, adapter_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    return adapter.product_data


@router.post("/",
             response_model=product_data.ProductData,
            )
async def create_product(
    project_id: str,
    adapter_id: str,
    product: Annotated[product_data.ProductData,
                    Body(examples=PRODUCT_LIST_EXAMPLE)]
) -> product_data.ProductData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    # TODO: only add if product does not exist, else raise error
    adapter.product_data.append(product)
    prodsys_backend.update_adapter(project_id, adapter)
    return product


@router.get(
    "/{product_id}",
    response_model=product_data.ProductData,
    responses={
        200: {
            "description": "Sucessfully returned product data",
            "content": {
                "application/json": {
                    "example": PRODUCT_LIST_EXAMPLE
                }
            }
        },
        404: {"description": "No product data found."}
    }
)
async def get_product(project_id: str, adapter_id: str, product_id: str):
    product = get_product_from_backend(project_id, adapter_id, product_id)
    return product


@router.put("/{product_id}", response_model=product_data.ProductData)
async def update_product(
    project_id: str,
    adapter_id: str,
    product_id: str,
    product: Annotated[product_data.ProductData,
                    Body(examples=PRODUCT_LIST_EXAMPLE)]
) -> product_data.ProductData:
    if product.ID != product_id:
        raise HTTPException(404, "Product ID must not be changed")
    # TODO: update product with saving to backend
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    adapter.product_data.append(product)
    return product



@router.delete("/{product_id}", response_model=str)
async def delete_product(project_id: str, adapter_id: str, product_id: str) -> str:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    product = get_product_from_backend(project_id, adapter_id, product_id)
    adapter.product_data.remove(product)
    prodsys_backend.update_adapter(project_id, adapter)
    return "Sucessfully deleted product with ID: " + product_id
