
import os
import uuid
from fastapi import  APIRouter, Query, HTTPException, status, Depends
from router import router_param_builder
from utils.auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
    oauth2_scheme,
    token_blacklist,
)
from utils.helper import ensure_exists
from router.dto.user import UserRegister, UserRegisterResponse, UserUpdate, UserFilters, UsersListResponse, UserResponse
from db import mongo_service
from utils.pagination import Pagination
from pymongo.errors import DuplicateKeyError, BulkWriteError, PyMongoError
from fastapi.security import OAuth2PasswordRequestForm

pagination = Pagination()

tag = os.path.splitext(os.path.basename(os.path.abspath(__file__)))[0]
router = APIRouter(**router_param_builder(tag))


@router.get("/api/v1/users", response_model=UsersListResponse)
def get_all_users(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=200),
    filters: UserFilters = Depends(),
):
    query = {}
    if filters.name:
        query["name"] = filters.name
    if filters.email:
        query["email"] = filters.email.strip().lower()
    if filters.status:
        query["status"] = filters.status

    total_data = mongo_service.count_documents("users", query)
    paging = pagination.get_paging(str(page), str(size))
    user_items = mongo_service.find_many(
        "users", query, paging.get("offset"), paging.get("limit")
    )
    paging_info = pagination.get_pagination_info(
        str(total_data), [], str(size), str(page)
    )
    return {"data": user_items, "pagination_info": paging_info}


@router.get("/api/v1/users/{user_id}")
def get_user_by_id(user_id: str):
    user = mongo_service.find_one("users", {"user_id": user_id})
    return ensure_exists(user, "User")


@router.put("/api/v1/users/{user_id}")
def update_user(user_id: str, payload: UserUpdate):
    update = {k: v for k, v in payload.dict().items() if v is not None}
    if not update:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )
    res = mongo_service.update_one("users", {"user_id": user_id}, update)
    if res.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    user = mongo_service.find_one("users", {"user_id": user_id})
    return user


@router.delete("/api/v1/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str):
    res = mongo_service.delete_one("users", {"user_id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return None


@router.post("/api/v1/auth/register", status_code=status.HTTP_201_CREATED, response_model=UserRegisterResponse)
def register(payload: UserRegister):
            
    email = payload.email.strip().lower()
    existing = mongo_service.find_one("users", {"email": email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    user_doc = {
        "user_id": str(uuid.uuid4()),
        "name": payload.name.strip(),
        "email": email,
        "prone": payload.phone.strip() if payload.phone else None,
        "status": payload.status,
        "password": get_password_hash(payload.password),
    }
    try:
        mongo_service.insert_one("users", user_doc)
    except DuplicateKeyError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate key error while registering user",
        ) from e
    except PyMongoError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while registering user",
        ) from e
    # Do not return password
    user_doc.pop("password", None)
    return {"status": status.HTTP_201_CREATED, "data": UserRegisterResponse}


@router.post("/api/v1/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # OAuth2 form fields: username, password
    email = form_data.username.strip().lower()
    user = mongo_service.find_one("users", {"email": email})
    if not user or not verify_password(form_data.password, user.get("password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    access_token = create_access_token({"sub": user["user_id"]})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/api/v1/auth/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user


@router.post("/api/v1/auth/logout")
def logout(token: str = Depends(oauth2_scheme)):
    # Add token to blacklist (demo). For production, consider short TTLs or server-side sessions.
    token_blacklist.add(token)
    return {"message": "Logged out"}
