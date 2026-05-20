from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response
import httpx
import os
import logging
import time
from typing import Any

from .router import router as v1_router

logger = logging.getLogger("aether.gateway")
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
app = FastAPI(
    title="Aether Gateway",
    version="1.0.0",
    description="Unified API gateway for Aether platform workflows.",
)

# Enable CORS to allow dashboard (localhost:3000) to call gateway APIs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.get("/")
def root() -> dict:
    return {
        "status": "ok",
        "service": "gateway",
        "health": "/health",
        "contracts": "/v1/contracts",
        "docs": "/docs",
    }


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted = {}
    sensitive = {"authorization", "cookie", "x-api-key"}
    for key, value in headers.items():
        redacted[key] = "[REDACTED]" if key.lower() in sensitive else value
    return redacted


def _safe_log_body(content_type: str | None, body: bytes, limit: int = 2048) -> Any:
    if not body:
        return None
    if content_type and "multipart/form-data" in content_type:
        return f"multipart/form-data ({len(body)} bytes)"
    if content_type and "application/json" in content_type:
        try:
            import json as _json

            payload = _json.loads(body.decode("utf-8"))
            if isinstance(payload, dict):
                for key in ("password", "token", "authorization", "secret", "api_key"):
                    if key in payload:
                        payload[key] = "[REDACTED]"
            return payload
        except Exception:
            pass
    text = body.decode("utf-8", errors="replace")
    return text[:limit] + ("..." if len(text) > limit else "")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started_at = time.perf_counter()
    body = await request.body()
    logger.info(
        "request start method=%s path=%s query=%s headers=%s body=%s",
        request.method,
        request.url.path,
        request.url.query,
        _redact_headers(dict(request.headers)),
        _safe_log_body(request.headers.get("content-type"), body),
    )

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(request.scope, receive)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request error method=%s path=%s", request.method, request.url.path)
        raise

    duration_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "request end method=%s path=%s status=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        getattr(response, "status_code", 0),
        duration_ms,
    )
    return response


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "gateway"}


# ---------------------------------------------------------------------------
# Auth proxy routes (no /v1 prefix) — forward to user_management service
# ---------------------------------------------------------------------------

USER_MANAGEMENT_URL = os.getenv("AETHER_USER_MANAGEMENT_URL", "http://localhost:8001")


from pydantic import BaseModel


class AuthRequest(BaseModel):
    username: str
    password: str


@app.post("/register")
async def register(auth: AuthRequest):
    """Proxy register request to user_management service."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{USER_MANAGEMENT_URL}/register",
                json=auth.dict(),
                timeout=10,
            )
            return response.json()
        except Exception as e:
            logger.error(f"Failed to proxy /register: {e}")
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail="User management service unavailable")


@app.post("/login")
async def login(auth: AuthRequest):
    """Proxy login request to user_management service."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{USER_MANAGEMENT_URL}/login",
                json=auth.dict(),
                timeout=10,
            )
            return response.json()
        except Exception as e:
            logger.error(f"Failed to proxy /login: {e}")
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail="User management service unavailable")


@app.get("/me")
async def get_me(authorization: str = Header(None)):
    """Proxy get current user to user_management service."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{USER_MANAGEMENT_URL}/me",
                headers={"Authorization": authorization},
                timeout=10,
            )
            return response.json()
        except Exception as e:
            logger.error(f"Failed to proxy /me: {e}")
            raise HTTPException(status_code=503, detail="User management service unavailable")


# ---------------------------------------------------------------------------
# App Validator proxy routes
# ---------------------------------------------------------------------------

APP_VALIDATOR_URL = os.getenv("AETHER_APP_VALIDATOR_URL", "http://localhost:8011")


@app.post("/validate")
async def validate_app(file: UploadFile = File(...)):
    """Proxy validate app to app_validator service."""
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
    
    content = await file.read()
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{APP_VALIDATOR_URL}/validate",
                files={"file": (file.filename, content, file.content_type)},
                timeout=30,
            )
            return response.json()
        except Exception as e:
            logger.error(f"Failed to proxy /validate: {e}")
            raise HTTPException(status_code=503, detail="App validator service unavailable")

