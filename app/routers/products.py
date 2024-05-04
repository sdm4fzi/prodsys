from typing import List, Annotated


from fastapi import APIRouter, Body
from prodsys.models import (
    product_data,
)
from app.dao import product_dao

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
            "content": {"application/json": {"example": PRODUCT_LIST_EXAMPLE}},
        },
        404: {"description": "No product data found."},
    },
)
async def get_products(project_id: str, adapter_id: str):
    return product_dao.get_products_from_backend(project_id, adapter_id)


@router.post(
    "/",
    response_model=product_data.ProductData,
)
async def create_product(
    project_id: str,
    adapter_id: str,
    product: Annotated[product_data.ProductData, Body(examples=PRODUCT_LIST_EXAMPLE)],
) -> product_data.ProductData:
    return product_dao.add_product_to_backend(project_id, adapter_id, product)


@router.get(
    "/{product_id}",
    response_model=product_data.ProductData,
    responses={
        200: {
            "description": "Sucessfully returned product data",
            "content": {"application/json": {"example": PRODUCT_LIST_EXAMPLE}},
        },
        404: {"description": "No product data found."},
    },
)
async def get_product(project_id: str, adapter_id: str, product_id: str):
    return product_dao.get_product_from_backend(project_id, adapter_id, product_id)


@router.put("/{product_id}", response_model=product_data.ProductData)
async def update_product(
    project_id: str,
    adapter_id: str,
    product_id: str,
    product: Annotated[product_data.ProductData, Body(examples=PRODUCT_LIST_EXAMPLE)],
) -> product_data.ProductData:
    return product_dao.update_product_in_backend(
        project_id, adapter_id, product_id, product
    )


@router.delete("/{product_id}", response_model=str)
async def delete_product(project_id: str, adapter_id: str, product_id: str) -> str:
    product_dao.delete_product_from_backend(project_id, adapter_id, product_id)
    return f"Deleted product with ID {product_id}"
