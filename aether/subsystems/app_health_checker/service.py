"""
service.py

FastAPI + CLI service for app health monitoring.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Dict, Optional
import threading

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .models import AppHealthRecord, HealthStatus
from .prober import AppHealthProber
from .scheduler import HealthCheckScheduler
from aether.kafka import topics

logger = logging.getLogger("aether.app_health_checker.service")


class RegisterTargetRequest(BaseModel):
    app_id: str
    app_version: str
    artifact_id: str
    vm_ip: str
    port: int = Field(..., ge=1, le=65535)
    health_path: str = "/health"
    failure_threshold: int = Field(default=3, ge=1)


class HealthCheckerService:
    def __init__(self, interval_seconds: int = 30, timeout_seconds: float = 3.0):
        self.records: Dict[str, AppHealthRecord] = {}
        self.kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self._kafka_producer = None
        self._consumer_thread: threading.Thread | None = None
        self._consumer_stop = threading.Event()
        self.prober = AppHealthProber(timeout_seconds=timeout_seconds)
        self.scheduler = HealthCheckScheduler(
            registry=self.records,
            prober=self.prober,
            on_probe=self._on_probe,
            interval_seconds=interval_seconds,
        )
        self._init_kafka_producer()

    def _key(self, app_id: str, artifact_id: str, vm_ip: str, port: int) -> str:
        return f"{app_id}:{artifact_id}:{vm_ip}:{port}"

    def register(self, request: RegisterTargetRequest) -> AppHealthRecord:
        record = AppHealthRecord(
            app_id=request.app_id,
            app_version=request.app_version,
            artifact_id=request.artifact_id,
            vm_ip=request.vm_ip,
            port=request.port,
            health_path=request.health_path,
            failure_threshold=request.failure_threshold,
        )
        self.records[self._key(request.app_id, request.artifact_id, request.vm_ip, request.port)] = record
        return record

    def unregister(self, app_id: str, artifact_id: str, vm_ip: str, port: int) -> bool:
        return self.records.pop(self._key(app_id, artifact_id, vm_ip, port), None) is not None

    def run_manual_check(self, app_id: Optional[str] = None) -> dict:
        probes = self.scheduler.run_once()
        if app_id:
            probes = [p for p in probes if p.app_id == app_id]

        return {
            "count": len(probes),
            "probes": [p.to_dict() for p in probes],
        }

    def summary(self) -> dict:
        by_status = {status.value: 0 for status in HealthStatus}
        for record in self.records.values():
            by_status[record.status.value] = by_status.get(record.status.value, 0) + 1

        return {
            "total": len(self.records),
            "by_status": by_status,
        }

    def _on_probe(self, record: AppHealthRecord, _probe) -> None:
        if record.status == HealthStatus.DOWN and record.consecutive_failures == record.failure_threshold:
            logger.warning(
                "app.unhealthy event candidate: app=%s artifact=%s endpoint=%s failures=%s",
                record.app_id,
                record.artifact_id,
                record.endpoint,
                record.consecutive_failures,
            )
            self._publish_event(
                topics.APP_UNHEALTHY,
                {
                    "event_type": "app.unhealthy",
                    "app_id": record.app_id,
                    "app_version": record.app_version,
                    "artifact_id": record.artifact_id,
                    "endpoint": record.endpoint,
                    "failures": record.consecutive_failures,
                    "detail": f"Artifact {record.artifact_id} is DOWN at {record.endpoint}",
                },
            )

    def _init_kafka_producer(self) -> None:
        try:
            from kafka import KafkaProducer  # type: ignore

            self._kafka_producer = KafkaProducer(
                bootstrap_servers=self.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                request_timeout_ms=5000,
            )
            logger.info("Kafka producer connected for health checker")
        except Exception as exc:
            self._kafka_producer = None
            logger.warning("Kafka producer unavailable in health checker: %s", exc)

    def _publish_event(self, topic: str, payload: dict) -> None:
        if not self._kafka_producer:
            return
        try:
            self._kafka_producer.send(topic, payload)
        except Exception as exc:
            logger.warning("Failed to publish event %s: %s", topic, exc)

    def start_event_listener(self) -> None:
        if self._consumer_thread and self._consumer_thread.is_alive():
            return
        self._consumer_stop.clear()
        self._consumer_thread = threading.Thread(target=self._consume_loop, daemon=True)
        self._consumer_thread.start()

    def stop_event_listener(self) -> None:
        self._consumer_stop.set()
        if self._consumer_thread:
            self._consumer_thread.join(timeout=2.0)

    def _consume_loop(self) -> None:
        while not self._consumer_stop.is_set():
            consumer = None
            try:
                from kafka import KafkaConsumer  # type: ignore

                consumer = KafkaConsumer(
                    topics.APP_DEPLOYED,
                    bootstrap_servers=self.kafka_bootstrap_servers,
                    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                    auto_offset_reset="latest",
                    enable_auto_commit=True,
                    group_id="aether-app-health-checker",
                )

                while not self._consumer_stop.is_set():
                    message_pack = consumer.poll(timeout_ms=1000)
                    for _tp, messages in message_pack.items():
                        for message in messages:
                            payload = message.value or {}
                            if payload.get("event_type") != "app.deployed":
                                continue
                            deployment = payload.get("deployment", {})
                            app_id = deployment.get("app_id")
                            app_version = deployment.get("app_version", "unknown")
                            for process in deployment.get("process_records", []):
                                req = RegisterTargetRequest(
                                    app_id=app_id,
                                    app_version=app_version,
                                    artifact_id=process.get("artifact_id", ""),
                                    vm_ip=process.get("vm_ip", ""),
                                    port=process.get("port", 0),
                                )
                                self.register(req)
                                logger.info("Auto-registered target from app.deployed: %s/%s", app_id, req.artifact_id)
            except Exception as exc:
                logger.warning("Kafka consumer unavailable in health checker (retrying): %s", exc)
                self._consumer_stop.wait(5.0)
            finally:
                if consumer:
                    consumer.close()


app = FastAPI(title="Aether App Health Checker", version="1.0.0")
svc = HealthCheckerService()


@app.on_event("startup")
def startup_event() -> None:
    svc.scheduler.start()
    svc.start_event_listener()


@app.on_event("shutdown")
def shutdown_event() -> None:
    svc.scheduler.stop()
    svc.stop_event_listener()


@app.post("/health/targets")
def register_target(request: RegisterTargetRequest) -> dict:
    return svc.register(request).to_dict()


@app.delete("/health/targets")
def unregister_target(app_id: str, artifact_id: str, vm_ip: str, port: int) -> dict:
    removed = svc.unregister(app_id, artifact_id, vm_ip, port)
    if not removed:
        raise HTTPException(status_code=404, detail="Target not found")
    return {"removed": True}


@app.get("/health/targets")
def list_targets() -> dict:
    return {
        "count": len(svc.records),
        "targets": [record.to_dict() for record in svc.records.values()],
    }


@app.post("/apps/{app_id}/health-check")
def manual_health_check(app_id: str) -> dict:
    return svc.run_manual_check(app_id=app_id)


@app.post("/health-check")
def manual_health_check_all() -> dict:
    return svc.run_manual_check()


@app.get("/health/summary")
def health_summary() -> dict:
    return svc.summary()


@app.get("/health")
def service_health() -> dict:
    return {"status": "ok", "service": "app_health_checker"}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="App Health Checker utility")
    parser.add_argument("--register", action="store_true", help="Register a target for health checks")
    parser.add_argument("--app-id", help="App ID")
    parser.add_argument("--app-version", default="unknown", help="App version")
    parser.add_argument("--artifact-id", help="Artifact ID")
    parser.add_argument("--vm-ip", help="VM IP")
    parser.add_argument("--port", type=int, help="Port")
    parser.add_argument("--health-path", default="/health", help="Health endpoint path")
    parser.add_argument("--check-now", action="store_true", help="Run one health check now")
    parser.add_argument("--json", action="store_true", help="Print JSON output")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.register:
        required = [args.app_id, args.artifact_id, args.vm_ip, args.port]
        if any(v is None for v in required):
            print("ERROR: --register requires --app-id --artifact-id --vm-ip --port", file=sys.stderr)
            return 1

        req = RegisterTargetRequest(
            app_id=args.app_id,
            app_version=args.app_version,
            artifact_id=args.artifact_id,
            vm_ip=args.vm_ip,
            port=args.port,
            health_path=args.health_path,
        )
        out = svc.register(req).to_dict()
    elif args.check_now:
        out = svc.run_manual_check(app_id=args.app_id)
    else:
        out = {
            "summary": svc.summary(),
            "targets": [record.to_dict() for record in svc.records.values()],
        }

    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(out)

    return 0


if __name__ == "__main__":
    sys.exit(main())
