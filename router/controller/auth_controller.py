import uuid
import os
import logging
from router import router_param_builder
from utils.pagination import Pagination
from fastapi import APIRouter, Query, HTTPException, status, Depends
from utils.auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
    oauth2_scheme,
    token_blacklist,
)
from router.dto.user import (
    UserRegister,
    UserRegisterResponse,
)
from db import mongo_service
from pymongo.errors import DuplicateKeyError, PyMongoError
from fastapi.security import OAuth2PasswordRequestForm
from pathlib import Path


ALLOWED_MIMES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_BYTES = 2 * 1024 * 1024  # 2 MB
AVATAR_DIR = Path("static") / "avatars"

pagination = Pagination()

tag = os.path.splitext(os.path.basename(os.path.abspath(__file__)))[0]
router = APIRouter(**router_param_builder(tag))

logger = logging.getLogger(__name__)


@router.post(
    "/api/v1/register",
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


@router.post("/api/v1/login")
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


@router.get("/api/v1/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user


@router.post("/api/v1/logout")
def logout(token: str = Depends(oauth2_scheme)):
    # Add token to blacklist (demo). For production, consider short TTLs or server-side sessions.
    token_blacklist.add(token)
    return {"message": "Logged out"}