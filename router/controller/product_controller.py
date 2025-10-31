import os
import uuid
import secrets
import re
from fastapi import (
    APIRouter,
    Query,
    HTTPException,
    status,
    Body,
    Depends,
    UploadFile,
    File,
)
from typing import List, Optional
from router import router_param_builder
from utils.helper import ensure_exists
from db import mongo_service
from utils.pagination import Pagination
from utils.auth import require_roles
from router.dto.product import (
    ProductBulkCreate,
    ProductCreate,
    ProductUpdate,
    ProductFilters,
    ProductsListResponse,
)
from pymongo.errors import DuplicateKeyError, BulkWriteError, PyMongoError
from pathlib import Path


ALLOWED_MIMES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_BYTES = 2 * 1024 * 1024  # 2 MB
PRODUCT_IMAGE_DIR = Path("static") / "products"

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
        pattern = re.escape(filters.name)
        query["name"] = {"$regex": pattern, "$options": "i"}

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


# @router.get("/api/v1/products/{product_id}")
# def get_product_by_id(product_id: str):
#     product = mongo_service.find_one("inventory", {"product_id": product_id})
#     return ensure_exists(product, "Product")


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


@router.put("/api/v1/{product_id}")
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

@router.delete("/api/v1/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: str, _=Depends(require_roles(["admin"]))):
    # Hapus file image jika ada sebelum delete dokumen
    product = mongo_service.find_one("inventory", {"product_id": product_id})
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
    image_url: Optional[str] = product.get("image_url")
    if image_url and image_url.startswith("/static/products/"):
        try:
            p = Path(image_url.lstrip("/")).resolve()
            if p.is_file() and PRODUCT_IMAGE_DIR.resolve() in p.parents:
                p.unlink(missing_ok=True)
        except Exception:
            pass

    res = mongo_service.delete_one("inventory", {"product_id": product_id})
    if res.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
    return None

@router.post("/api/v1/{product_id}/image")
async def upload_product_image(
    product_id: str,
    file: UploadFile = File(...),
    _=Depends(require_roles(["admin"])),
):
    # Pastikan product ada
    product = mongo_service.find_one("inventory", {"product_id": product_id})
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    # Validasi file
    if file.content_type not in ALLOWED_MIMES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large (max 2MB)")

    # Simpan file
    PRODUCT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    ext = ALLOWED_MIMES[file.content_type]
    filename = f"{secrets.token_urlsafe(16)}.{ext}"
    out_path = PRODUCT_IMAGE_DIR / filename
    with open(out_path, "wb") as f:
        f.write(content)

    # Hapus image lama jika ada (dan berada di folder yang diizinkan)
    old_url: Optional[str] = product.get("image_url")
    if old_url and old_url.startswith("/static/products/"):
        try:
            old_path = Path(old_url.lstrip("/")).resolve()
            if old_path.is_file() and PRODUCT_IMAGE_DIR.resolve() in old_path.parents:
                old_path.unlink(missing_ok=True)
        except Exception:
            pass

    # Update DB
    image_url = f"/static/products/{filename}"
    mongo_service.update_one("inventory", {"product_id": product_id}, {"image_url": image_url})
    return {"image_url": image_url}

@router.delete("/api/v1/{product_id}/image", status_code=status.HTTP_204_NO_CONTENT)
def delete_product_image(
    product_id: str,
    _=Depends(require_roles(["admin"])),
):
    product = mongo_service.find_one("inventory", {"product_id": product_id})
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    image_url: Optional[str] = product.get("image_url")
    if image_url and image_url.startswith("/static/products/"):
        try:
            p = Path(image_url.lstrip("/")).resolve()
            if p.is_file() and PRODUCT_IMAGE_DIR.resolve() in p.parents:
                p.unlink(missing_ok=True)
        except Exception:
            pass

    mongo_service.update_one("inventory", {"product_id": product_id}, {"image_url": None})
    return None