import os
import uuid
from fastapi import APIRouter, Query, HTTPException, status, Body, Depends
from typing import List
from router import router_param_builder
from utils.helper import ensure_exists
from db import mongo_service
from utils.pagination import Pagination
from router.dto.product import ProductBulkCreate, ProductCreate, ProductUpdate, ProductFilters, ProductsListResponse
from pymongo.errors import DuplicateKeyError, BulkWriteError, PyMongoError

pagination = Pagination()

tag = os.path.splitext(os.path.basename(os.path.abspath(__file__)))[0]
router = APIRouter(**router_param_builder(tag))

@router.get("/api/v1/products", response_model=ProductsListResponse)
def get_all_products(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=200),
    filters: ProductFilters = Depends(),
):
    query = {}
    if filters.name:
        query["name"] = filters.name

    total_data = mongo_service.count_documents("inventory", query)
    paging = pagination.get_paging(str(page), str(size))
    product_items = mongo_service.find_many(
        "inventory", query, paging.get("offset"), paging.get("limit")
    )
    # result = [convert_object_id(item) for item in product_items]
    paging_info = pagination.get_pagination_info(
        str(total_data), [], str(size), str(page)
    )
    return {"data": product_items, "pagination_info": paging_info}


@router.get("/api/v1/products/{product_id}")
def get_product_by_id(product_id: str):
    product = mongo_service.find_one("inventory", {"product_id": product_id})
    return ensure_exists(product, "Product")


@router.post(
    "/api/v1/products",
    response_model=ProductBulkCreate,
    status_code=status.HTTP_201_CREATED,
)
def create_products(products: List[ProductCreate] = Body(..., min_items=1)):
    product_docs = []
    for p in products:
        doc = p.dict()
        doc["product_id"] = str(uuid.uuid4())
        product_docs.append(doc)
    try:
        # Will raise on failure; on success, we don't need the returned IDs since we generate product_id
        mongo_service.insert_many("inventory", product_docs)
    except DuplicateKeyError as e:
        # Likely due to a unique index conflict (e.g., product_id or another unique field)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate key error while creating products",
        ) from e
    except BulkWriteError as e:
        # Validation or write errors in one or more docs
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bulk write error while creating products",
        ) from e
    except PyMongoError as e:
        # Catch-all for other Mongo errors (network, server, write concern, etc.)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while creating products",
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while creating products",
        ) from e

    return {"status": status.HTTP_201_CREATED, "data": product_docs}


@router.put("/api/v1/products/{product_id}")
def update_product(product_id: str, payload: ProductUpdate):
    update = {k: v for k, v in payload.dict().items() if v is not None}
    if not update:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )
    res = mongo_service.update_one("inventory", {"product_id": product_id}, update)
    if res.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
    product = mongo_service.find_one("inventory", {"product_id": product_id})
    return product


@router.delete("/api/v1/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: str):
    res = mongo_service.delete_one("inventory", {"product_id": product_id})
    if res.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
    return None

