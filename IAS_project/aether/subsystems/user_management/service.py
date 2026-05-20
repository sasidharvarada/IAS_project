"""
platform/subsystems/user_management/service.py

FastAPI application entry point for the User Management subsystem.

Responsibilities:
  - Creates PostgreSQL tables on startup (SQLAlchemy)
  - Starts an optional Kafka producer for user.events
  - Exposes CORS so the dashboard can call it directly
  - Includes all routes from routes.py

Run (development):
    cd platform
    uvicorn subsystems.user_management.service:app --reload --port 8000

Run (production / systemd):
    uvicorn subsystems.user_management.service:app --host 0.0.0.0 --port 8000

NOTE: Until the Gateway is implemented this service runs on port 8000 directly.
      When Gateway is ready, move this to an internal port (e.g. 8001) and let
      the Gateway proxy /register /login /me /api-keys here.
"""

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .models import Base, engine
from .routes import router

# Load .env from the platform root (two levels up from this file)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("user_management")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:3003,http://localhost:5173",
).split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("User Management: creating DB tables if not exists...")
    Base.metadata.create_all(bind=engine)
    logger.info("User Management: DB ready.")

    # Kafka producer — optional; service starts fine without Kafka
    try:
        from kafka import KafkaProducer  # type: ignore

        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            request_timeout_ms=5000,
        )
        app.state.kafka_producer = producer
        logger.info(f"User Management: Kafka producer connected to {KAFKA_BOOTSTRAP}")
    except Exception as exc:
        app.state.kafka_producer = None
        logger.warning(f"User Management: Kafka unavailable ({exc}). user.events will be skipped.")

    yield

    # --- Shutdown ---
    if getattr(app.state, "kafka_producer", None):
        app.state.kafka_producer.close()
        logger.info("User Management: Kafka producer closed.")


app = FastAPI(
    title="AetherAgents — User Management",
    version="1.0.0",
    description="Handles registration, login, JWT sessions, API keys, and RBAC.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted = {}
    sensitive = {"authorization", "cookie", "x-api-key"}
    for key, value in headers.items():
        redacted[key] = "[REDACTED]" if key.lower() in sensitive else value
    return redacted


def _safe_log_body(content_type: str | None, body: bytes, limit: int = 2048):
    if not body:
        return None
    if content_type and "application/json" in content_type:
        try:
            payload = json.loads(body.decode("utf-8"))
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

    async def receive():
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
def health():
    return {"status": "ok", "service": "user_management"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("subsystems.user_management.service:app", host="0.0.0.0", port=port, reload=False)
