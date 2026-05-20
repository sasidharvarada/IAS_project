"""
service.py

FastAPI + CLI entry point for notification service.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Optional
import asyncio

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr

from .channels import SMTPEmailChannel, SMTPSettings
from aether.kafka import topics

logger = logging.getLogger("aether.notification_service")


class EmailNotificationRequest(BaseModel):
    to_email: EmailStr
    subject: str
    body: str


class PlatformEventRequest(BaseModel):
    event_type: str
    recipient_email: EmailStr
    app_id: str
    app_version: Optional[str] = None
    detail: Optional[str] = None


class NotificationService:
    def __init__(self):
        self._channel: Optional[SMTPEmailChannel] = None

    def _channel_or_raise(self) -> SMTPEmailChannel:
        if self._channel is None:
            settings = SMTPSettings.from_env()
            self._channel = SMTPEmailChannel(settings)
        return self._channel

    def send_email(self, req: EmailNotificationRequest) -> dict:
        channel = self._channel_or_raise()
        return channel.send_email(req.to_email, req.subject, req.body)

    def send_event_email(self, req: PlatformEventRequest) -> dict:
        subject = f"[Aether] {req.event_type} - {req.app_id}"
        body_lines = [
            f"Event: {req.event_type}",
            f"App: {req.app_id}",
        ]
        if req.app_version:
            body_lines.append(f"Version: {req.app_version}")
        if req.detail:
            body_lines.append(f"Detail: {req.detail}")

        body = "\n".join(body_lines)
        return self.send_email(
            EmailNotificationRequest(
                to_email=req.recipient_email,
                subject=subject,
                body=body,
            )
        )

    def send_platform_event(self, payload: dict) -> None:
        alert_email = os.getenv("AETHER_ALERT_EMAIL", "")
        if not alert_email:
            return
        request = PlatformEventRequest(
            event_type=payload.get("event_type", "platform.event"),
            recipient_email=alert_email,
            app_id=payload.get("app_id", "unknown"),
            app_version=payload.get("app_version"),
            detail=payload.get("detail"),
        )
        self.send_event_email(request)


class KafkaNotificationConsumer:
    def __init__(self, service: NotificationService):
        self.service = service

    async def consume(self) -> None:
        try:
            from kafka import KafkaConsumer  # type: ignore
        except Exception as exc:
            logger.warning("Kafka unavailable in notification service: %s", exc)
            return

        consumer = KafkaConsumer(
            topics.APP_UNHEALTHY,
            topics.APP_LIFECYCLE,
            topics.APP_DEPLOYED,
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=True,
            group_id="aether-notification-service",
        )
        try:
            while True:
                message_pack = consumer.poll(timeout_ms=1000)
                for _tp, messages in message_pack.items():
                    for message in messages:
                        payload = message.value or {}
                        self.service.send_platform_event(payload)
                await asyncio.sleep(0.05)
        finally:
            consumer.close()


async def app_lifespan(app: FastAPI):
    consumer = KafkaNotificationConsumer(svc)
    task = asyncio.create_task(consumer.consume())
    yield
    task.cancel()


app = FastAPI(title="Aether Notification Service", version="1.0.0", lifespan=app_lifespan)
svc = NotificationService()


@app.post("/notify/email")
def notify_email(request: EmailNotificationRequest) -> dict:
    try:
        return svc.send_email(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to send email: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to send email") from exc


@app.post("/notify/event")
def notify_event(request: PlatformEventRequest) -> dict:
    try:
        return svc.send_event_email(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to send event email: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to send event notification") from exc


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "notification_service"}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Send Aether notifications via SMTP")
    parser.add_argument("--to", help="Destination email address")
    parser.add_argument("--subject", help="Email subject")
    parser.add_argument("--body", help="Email body")
    parser.add_argument("--json", action="store_true", help="Print output as JSON")

    args = parser.parse_args()

    if not args.to or not args.subject or not args.body:
        print("ERROR: --to --subject --body are required", file=sys.stderr)
        return 1

    logging.basicConfig(level=logging.INFO)

    try:
        result = svc.send_email(
            EmailNotificationRequest(to_email=args.to, subject=args.subject, body=args.body)
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
