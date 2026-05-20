from __future__ import annotations

import asyncio
import json
import logging
import os
from fastapi import FastAPI

from aether.kafka import topics
from .routes import router, controller

logger = logging.getLogger("aether.lifecycle_manager.service")


class KafkaLifecycleConsumer:
    async def consume(self) -> None:
        try:
            from kafka import KafkaConsumer  # type: ignore
        except Exception as exc:
            logger.warning("Kafka unavailable in lifecycle manager consumer: %s", exc)
            return

        consumer = KafkaConsumer(
            topics.APP_UNHEALTHY,
            topics.APP_DEPLOYED,
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=True,
            group_id="aether-lifecycle-manager",
        )
        try:
            while True:
                message_pack = consumer.poll(timeout_ms=1000)
                for _tp, messages in message_pack.items():
                    for message in messages:
                        payload = message.value or {}
                        event_type = payload.get("event_type")
                        if event_type == "app.deployed":
                            deployment = payload.get("deployment", {})
                            controller.register_deployment_dict(deployment)
                        elif event_type == "app.unhealthy":
                            controller.restart(
                                payload.get("app_id", ""),
                                app_version=payload.get("app_version"),
                                reason=payload.get("detail", "Health-check threshold exceeded"),
                            )
                await asyncio.sleep(0.05)
        finally:
            consumer.close()


async def app_lifespan(app: FastAPI):
    consumer = KafkaLifecycleConsumer()
    task = asyncio.create_task(consumer.consume())
    yield
    task.cancel()


app = FastAPI(
    title="AetherAgents Lifecycle Manager",
    description="Controls start, stop, restart, scale, and rollback of deployed apps",
    version="1.0.0",
    lifespan=app_lifespan,
)

app.include_router(router, prefix="/apps", tags=["Lifecycle"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "lifecycle_manager"}
