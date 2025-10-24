import os
import uuid
import logging
from fastapi import APIRouter, Query, HTTPException, status, Depends, UploadFile, File
from router import router_param_builder
from utils.auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
    oauth2_scheme,
    token_blacklist,
    require_roles
)
from utils.helper import ensure_exists
from router.dto.user import (
    UserRegister,
    UserRegisterResponse,
    UserUpdate,
    UserFilters,
    UsersListResponse,
    UserResponse,
)
from db import mongo_service
from utils.pagination import Pagination
from pymongo.errors import DuplicateKeyError, BulkWriteError, PyMongoError
from fastapi.security import OAuth2PasswordRequestForm
from typing import Optional
import secrets
from pathlib import Path

ALLOWED_MIMES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_BYTES = 2 * 1024 * 1024  # 2 MB
AVATAR_DIR = Path("static") / "avatars"

pagination = Pagination()

tag = os.path.splitext(os.path.basename(os.path.abspath(__file__)))[0]
router = APIRouter(**router_param_builder(tag))

logger = logging.getLogger(__name__)


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
def delete_user(user_id: str, _=Depends(require_roles(["admin"]))):
    # Bersihkan avatar file jika ada
    user = mongo_service.find_one("users", {"user_id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    avatar_url: Optional[str] = user.get("avatar_url")
    if avatar_url and avatar_url.startswith("/static/avatars/"):
        try:
            p = Path(avatar_url.lstrip("/")).resolve()
            if p.is_file() and AVATAR_DIR.resolve() in p.parents:
                p.unlink(missing_ok=True)
        except Exception:
            pass

    res = mongo_service.delete_one("users", {"user_id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return None


@router.post(
    "/api/v1/auth/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserRegisterResponse,
)
def register(payload: UserRegister):

    email = payload.email.strip().lower()
    existing = mongo_service.find_one("users", {"email": email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    roles = payload.roles if payload.roles else ['user']
    if roles:
        roles = sorted({r.strip().lower() for r in roles if r and r.strip()})
        roles = list(roles) if roles else ['user']
    user_doc = {
        "user_id": str(uuid.uuid4()),
        "name": payload.name.strip(),
        "email": email,
        "phone": payload.phone.strip() if payload.phone else None,
        "status": payload.status,
        "roles": roles,
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
    return {"status": status.HTTP_201_CREATED, "data": user_doc}


@router.post("/api/v1/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    email = form_data.username.strip().lower()
    logger.info(f"Attempting login for email: {email}")
    user = mongo_service.find_one("users", {"email": email})
    logger.info(f"User result: {'found' if user else 'not found'}")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not verify_password(form_data.password, user.get("password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
        )
    roles = user.get("roles") or ["user"]
    access_token = create_access_token({"sub": user["user_id"], "roles": roles})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/api/v1/auth/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user


@router.post("/api/v1/auth/logout")
def logout(token: str = Depends(oauth2_scheme)):
    # Add token to blacklist (demo). For production, consider short TTLs or server-side sessions.
    token_blacklist.add(token)
    return {"message": "Logged out"}

def _is_admin(u: dict) -> bool:
    roles = u.get("roles") or []
    return "admin" in roles

@router.post("/api/v1/users/{user_id}/avatar")
async def upload_avatar(
    user_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    # Authorization: owner or admin
    if (current_user.get("user_id") != user_id) and (not _is_admin(current_user)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    if file.content_type not in ALLOWED_MIMES:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 2MB)")

    # Filename and path
    ext = ALLOWED_MIMES[file.content_type]
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{secrets.token_urlsafe(16)}.{ext}"
    out_path = AVATAR_DIR / filename

    # Save file
    with open(out_path, "wb") as f:
        f.write(content)

    # Remove old avatar if exists (and is inside our avatar dir)
    user = mongo_service.find_one("users", {"user_id": user_id})
    old_url: Optional[str] = user.get("avatar_url") if user else None
    if old_url and old_url.startswith("/static/avatars/"):
        try:
            old_path = Path(old_url.lstrip("/"))
            if old_path.is_file() and old_path.resolve().is_file() and AVATAR_DIR.resolve() in old_path.resolve().parents:
                old_path.unlink(missing_ok=True)  # Python 3.8+: use try/except if missing_ok unsupported
        except Exception:
            pass

    avatar_url = f"/static/avatars/{filename}"
    mongo_service.update_one("users", {"user_id": user_id}, {"avatar_url": avatar_url})

    return {"avatar_url": avatar_url}

@router.delete("/api/v1/users/{user_id}/avatar", status_code=status.HTTP_204_NO_CONTENT)
def delete_avatar(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    if (current_user.get("user_id") != user_id) and (not _is_admin(current_user)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    user = mongo_service.find_one("users", {"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    avatar_url = user.get("avatar_url")
    if avatar_url and avatar_url.startswith("/static/avatars/"):
        try:
            p = Path(avatar_url.lstrip("/"))
            if p.is_file() and AVATAR_DIR.resolve() in p.resolve().parents:
                p.unlink(missing_ok=True)
        except Exception:
            pass

    mongo_service.update_one("users", {"user_id": user_id}, {"avatar_url": None})
    return None