from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List

class User(BaseModel):
    user_id: Optional[str] = None
    name: str
    email: str
    phone: Optional[str] = None
    created_at: Optional[str] = None
    status: Optional[str] = "active"


class UserCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    created_at: Optional[str] = None
    status: Optional[str] = "active"


class UserRegister(BaseModel):
    name: str
    email: str
    password: str
    phone: Optional[str] = None
    status: Optional[str] = "active"


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None


class UserFilters(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None

class UserResponse(BaseModel):
    user_id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    created_at: Optional[datetime] = Field(None, alias="created_at")
    updated_at: Optional[datetime] = Field(None, alias="updated_at")
    status: Optional[str] = None
    
class UsersListResponse(BaseModel):
    data: List[UserResponse]
    pagination_info: dict
    
class UserRegisterResponse(BaseModel):
    data: UserResponse
    status: int