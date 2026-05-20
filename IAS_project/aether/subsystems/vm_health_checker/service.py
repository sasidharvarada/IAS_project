from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from urllib import error, request

from fastapi import FastAPI

from aether.kafka import topics

logger = logging.getLogger("aether.vm_health_checker")


class VMHealthCheckerService:
    def __init__(self, vm_pool_path: str = "infra/vm_pool.json", interval_seconds: int = 30):
        self.vm_pool_path = Path(vm_pool_path)
        self.interval_seconds = max(5, interval_seconds)
        self.kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self._producer = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.last_snapshot: dict = {"vms": []}
        self._init_kafka()

    def _init_kafka(self) -> None:
        try:
            from kafka import KafkaProducer  # type: ignore

            self._producer = KafkaProducer(
                bootstrap_servers=self.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                request_timeout_ms=5000,
            )
        except Exception as exc:
            self._producer = None
            logger.warning("Kafka unavailable in vm_health_checker: %s", exc)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.last_snapshot = self.collect_snapshot()
                self.publish_snapshot(self.last_snapshot)
            except Exception as exc:
                logger.warning("vm health loop error: %s", exc)
            self._stop.wait(self.interval_seconds)

    def collect_snapshot(self) -> dict:
        if not self.vm_pool_path.exists():
            return {"vms": [], "error": f"{self.vm_pool_path} missing"}
        data = json.loads(self.vm_pool_path.read_text(encoding="utf-8"))
        vms = []
        for vm in data.get("vms", []):
            host = vm.get("ip") or vm.get("host") or "localhost"
            status = self._probe_host(host)
            vms.append(
                {
                    "name": vm.get("name", vm.get("label", host)),
                    "ip": host,
                    "roles": vm.get("roles", []),
                    "status": status,
                    "checked_at": time.time(),
                }
            )
        return {"vms": vms}

    def _probe_host(self, host: str) -> str:
        endpoint = f"http://{host}:8000/health"
        req = request.Request(endpoint, method="GET")
        try:
            with request.urlopen(req, timeout=1.5) as response:
                return "healthy" if response.getcode() == 200 else "degraded"
        except error.URLError:
            return "unreachable"

    def publish_snapshot(self, snapshot: dict) -> None:
        if not self._producer:
            return
        payload = {"event_type": "vm.health", "snapshot": snapshot}
        self._producer.send(topics.APP_LIFECYCLE, payload)


app = FastAPI(title="Aether VM Health Checker", version="1.0.0")
svc = VMHealthCheckerService(
    vm_pool_path=os.getenv("AETHER_VM_POOL_PATH", "infra/vm_pool.json"),
    interval_seconds=int(os.getenv("AETHER_VM_HEALTH_INTERVAL_SECONDS", "30")),
)


@app.on_event("startup")
def startup() -> None:
    svc.start()


@app.on_event("shutdown")
def shutdown() -> None:
    svc.stop()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "vm_health_checker"}


@app.get("/snapshot")
def snapshot() -> dict:
    return svc.last_snapshot

