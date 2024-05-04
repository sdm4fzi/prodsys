from fastapi import HTTPException
from prodsys.models import product_data
from app.dependencies import prodsys_backend


def get_products_from_backend(
    project_id: str, adapter_id: str
) -> product_data.ProductData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    return adapter.product_data


def get_product_from_backend(
    project_id: str, adapter_id: str, product_id: str
) -> product_data.ProductData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for product in adapter.product_data:
        if product.ID == product_id:
            return product
    raise HTTPException(404, f"Product with ID {product_id} not found.")


def add_product_to_backend(
    project_id: str, adapter_id: str, product: product_data.ProductData
) -> product_data.ProductData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    if get_product_from_backend(project_id, adapter_id, product.ID):
        raise HTTPException(
            404, f"Product with ID {product.ID} already exists. Try updating instead."
        )
    adapter.product_data.append(product)
    prodsys_backend.update_adapter(project_id, adapter_id, adapter)
    return product


def update_product_in_backend(
    project_id: str, adapter_id: str, product_id: str, product: product_data.ProductData
) -> product_data.ProductData:
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for idx, existing_product in enumerate(adapter.product_data):
        if existing_product.ID == product_id:
            adapter.product_data[idx] = product
            prodsys_backend.update_adapter(project_id, adapter_id, adapter)
            return product
    raise HTTPException(404, f"Product with ID {product_id} not found.")


def delete_product_from_backend(project_id: str, adapter_id: str, product_id: str):
    adapter = prodsys_backend.get_adapter(project_id, adapter_id)
    for idx, product in enumerate(adapter.product_data):
        if product.ID == product_id:
            adapter.product_data.pop(idx)
            prodsys_backend.update_adapter(project_id, adapter_id, adapter)
            return
