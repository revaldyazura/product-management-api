from fastapi import HTTPException, status
from typing import Optional

def convert_object_id(data):
    # Do not surface Mongo's internal _id in API responses
    if "_id" in data:
        data.pop("_id", None)
    return data

def ensure_exists(doc: Optional[dict], entity: str):
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'{entity} not found')
    return convert_object_id(doc)

def _is_admin(u: dict) -> bool:
    roles = u.get("roles") or []
    return "admin" in roles