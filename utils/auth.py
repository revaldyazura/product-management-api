from datetime import datetime, timedelta
from fastapi import  HTTPException, status, Depends
from typing import Optional, Set, Callable, List
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError
from db import mongo_service
from utils.helper import convert_object_id
from settings import settings

# Auth setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="user/controller/api/v1/auth/login")
JWT_SECRET = settings.jwt_secret_key or "dev-secret-change-me"
JWT_ALG = settings.jwt_algorithm
ACCESS_EXPIRE_MINUTES = int(settings.access_token_expire_minutes)

# Very simple in-memory blacklist for demo logout (stateless JWTs)
token_blacklist: Set[str] = set()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALG)
    return token


def get_current_user(token: str = Depends(oauth2_scheme)):
    if token in token_blacklist:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = mongo_service.find_one('users', {'user_id': user_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    # Remove password before returning
    user['roles'] = user.get('roles', ['user'])
    user.pop('password', None)
    return user

def require_roles(allowed: List[str]) -> Callable:
    """
    Dependency untuk membatasi akses berdasarkan roles.
    Usage:
      def handler(..., _=Depends(require_roles(['admin']))): ...
    """
    def _dep(current_user: dict = Depends(get_current_user)):
        roles = current_user.get('roles') or []
        if not any(r in roles for r in allowed):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return current_user
    return _dep