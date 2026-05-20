"""
platform/subsystems/user_management/auth.py

Password hashing (bcrypt), JWT creation/verification, and API key helpers.
Also provides FastAPI dependencies for extracting the current user
from either a Bearer JWT or an X-API-Key header.
"""

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
import bcrypt
from sqlalchemy.orm import Session as DBSession

from .models import APIKey, Session, User, get_db

# --- Config (override via environment variables) ---
JWT_SECRET: str = os.getenv("JWT_SECRET", "CHANGE_THIS_IN_PRODUCTION")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
API_KEY_PREFIX: str = "sk-ae-"

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# --- Password helpers ---

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# --- JWT helpers ---

def create_access_token(user_id: str, username: str, role: str) -> tuple[str, str]:
    """
    Creates a signed JWT and returns (token, jti).
    The jti is stored in the Session table so individual tokens can be revoked.
    """
    jti = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "jti": jti,
        "exp": expires,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, jti


# --- API key helpers ---

def generate_api_key() -> tuple[str, str, str]:
    """
    Generates a new API key.
    Returns (plaintext_key, sha256_hash, display_prefix).
    Only the hash is stored; the plaintext is shown to the user once.
    """
    raw = secrets.token_urlsafe(32)
    key = f"{API_KEY_PREFIX}{raw}"
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    prefix = key[:12]
    return key, key_hash, prefix


def _hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# --- FastAPI auth dependencies ---

def _user_from_jwt(token: str, db: DBSession) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        jti: Optional[str] = payload.get("jti")
        if not user_id or not jti:
            raise exc
    except JWTError:
        raise exc

    session = db.query(Session).filter_by(jti=jti, is_active=True).first()
    if not session:
        raise exc

    user = db.query(User).filter_by(id=user_id, is_active=True).first()
    if not user:
        raise exc
    return user


def _user_from_api_key(key: str, db: DBSession) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )
    key_hash = _hash_api_key(key)
    api_key_obj = db.query(APIKey).filter_by(key_hash=key_hash, is_active=True).first()
    if not api_key_obj:
        raise exc

    # Update last-used timestamp
    api_key_obj.last_used_at = datetime.utcnow()
    db.commit()

    user = db.query(User).filter_by(id=api_key_obj.user_id, is_active=True).first()
    if not user:
        raise exc
    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_header),
    db: DBSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency: resolves the current user from either:
      - Authorization: Bearer <jwt>
      - X-API-Key: sk-ae-...
    Raises 401 if neither is provided or both are invalid.
    """
    if credentials:
        return _user_from_jwt(credentials.credentials, db)
    if api_key:
        return _user_from_api_key(api_key, db)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Provide a Bearer token or X-API-Key header.",
    )
