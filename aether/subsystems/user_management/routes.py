"""
platform/subsystems/user_management/routes.py

REST routes for the User Management subsystem.

Endpoints:
  POST /register          — create a new user account
  POST /login             — authenticate and receive a JWT
  GET  /me                — get current user profile (JWT or API key required)
  POST /api-keys          — create a new API key (returned once in plaintext)
  GET  /api-keys          — list active API keys for current user (prefix only)
  DELETE /api-keys/{id}   — revoke an API key
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from .auth import (
    create_access_token,
    generate_api_key,
    get_current_user,
    hash_password,
    verify_password,
)
from .models import APIKey, Role, Session, User, get_db

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    role: Role = Role.developer


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    role: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: Optional[str]
    role: str
    created_at: datetime
    is_active: bool


class CreateAPIKeyRequest(BaseModel):
    label: str = "default"


class APIKeyResponse(BaseModel):
    id: str
    prefix: str
    label: str
    created_at: datetime
    last_used_at: Optional[datetime]
    is_active: bool


class CreateAPIKeyFullResponse(APIKeyResponse):
    key: str  # plaintext — shown only once at creation


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: DBSession = Depends(get_db)):
    """Create a new user. Publishes user.events:registered to Kafka."""
    if db.query(User).filter_by(username=req.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    if req.email and db.query(User).filter_by(email=req.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
        role=req.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.value,
        created_at=user.created_at,
        is_active=user.is_active,
    )


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request, db: DBSession = Depends(get_db)):
    """Authenticate and return a JWT. Stores the session (jti) for revocation support."""
    user = db.query(User).filter_by(username=req.username, is_active=True).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token, jti = create_access_token(user.id, user.username, user.role.value)

    expire_hours = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
    session = Session(
        user_id=user.id,
        jti=jti,
        expires_at=datetime.utcnow() + timedelta(hours=expire_hours),
    )
    db.add(session)
    db.commit()

    # Publish to Kafka user.events if producer is available
    producer = getattr(request.app.state, "kafka_producer", None)
    if producer:
        producer.send("user.events", {"event": "login", "user_id": user.id, "username": user.username})

    return TokenResponse(
        token=token,
        user_id=user.id,
        username=user.username,
        role=user.role.value,
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return profile of the currently authenticated user."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role.value,
        created_at=current_user.created_at,
        is_active=current_user.is_active,
    )


@router.post("/api-keys", response_model=CreateAPIKeyFullResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
    req: CreateAPIKeyRequest,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """
    Generate a new API key for the current user.
    The plaintext key is returned ONCE — it cannot be recovered later.
    """
    plaintext, key_hash, prefix = generate_api_key()
    api_key = APIKey(
        user_id=current_user.id,
        key_hash=key_hash,
        prefix=prefix,
        label=req.label,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return CreateAPIKeyFullResponse(
        id=api_key.id,
        prefix=api_key.prefix,
        label=api_key.label,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        is_active=api_key.is_active,
        key=plaintext,
    )


@router.get("/api-keys", response_model=list[APIKeyResponse])
def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """List all active API keys for the current user (prefix only, no secrets)."""
    keys = db.query(APIKey).filter_by(user_id=current_user.id, is_active=True).all()
    return [
        APIKeyResponse(
            id=k.id,
            prefix=k.prefix,
            label=k.label,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            is_active=k.is_active,
        )
        for k in keys
    ]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Revoke (soft-delete) an API key. The key immediately stops working."""
    key = db.query(APIKey).filter_by(
        id=key_id, user_id=current_user.id, is_active=True
    ).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    key.is_active = False
    db.commit()
