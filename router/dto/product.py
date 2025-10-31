from datetime import datetime
from fastapi import Query
from pydantic import BaseModel, Field
from typing import Optional, List


class Product(BaseModel):
    product_id: Optional[str] = None
    name: str
    category: str
    description: str
    stock: int
    unit_price: float
    low_stock: int
    image_url: Optional[str] = None
    status: str = "active"


class ProductCreate(BaseModel):
    name: str
    category: str
    description: str
    stock: int
    unit_price: float
    low_stock: int
    image_url: Optional[str] = None
    status: str = "active"


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    unit_price: Optional[float] = None
    description: Optional[str] = None
    low_stock: Optional[int] = None
    status: Optional[str] = None



class ProductFilters:
    def __init__(
        self,
        name: Optional[str] = Query(None),
    ):
        self.name = name

class ProductResponse(BaseModel):
    product_id: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    stock: Optional[int] = None
    unit_price: Optional[float] = None
    low_stock: Optional[int] = None
    image_url: Optional[str] = None
    created_at: Optional[datetime] = Field(None, alias="created_at")
    updated_at: Optional[datetime] = Field(None, alias="updated_at")
    status: Optional[str] = None


class ProductsListResponse(BaseModel):
    data: List[ProductResponse]
    pagination_info: dict


class ProductBulkCreate(BaseModel):
    data: List[ProductResponse]
    status: int


class Config:
    allow_population_by_field_name = True
