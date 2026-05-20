"""
prober.py

HTTP prober for app /health endpoints.
"""

from __future__ import annotations

import json
import time
from urllib import error, request

from .models import AppHealthRecord, ProbeResult


class AppHealthProber:
    def __init__(self, timeout_seconds: float = 3.0):
        self.timeout_seconds = timeout_seconds

    def probe(self, record: AppHealthRecord) -> ProbeResult:
        started = time.perf_counter()

        try:
            req = request.Request(record.endpoint, method="GET")
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="ignore")
                status_code = response.getcode()

            elapsed_ms = (time.perf_counter() - started) * 1000.0

            is_healthy = status_code == 200
            detail = "ok" if is_healthy else f"health endpoint returned status {status_code}"

            if is_healthy and body:
                try:
                    payload = json.loads(body)
                    if isinstance(payload, dict) and payload.get("status") not in (None, "ok", "healthy"):
                        is_healthy = False
                        detail = f"health payload status={payload.get('status')}"
                except json.JSONDecodeError:
                    pass

            return ProbeResult(
                app_id=record.app_id,
                artifact_id=record.artifact_id,
                vm_ip=record.vm_ip,
                port=record.port,
                response_time_ms=round(elapsed_ms, 2),
                http_status=status_code,
                healthy=is_healthy,
                detail=detail,
            )
        except error.URLError as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            return ProbeResult(
                app_id=record.app_id,
                artifact_id=record.artifact_id,
                vm_ip=record.vm_ip,
                port=record.port,
                response_time_ms=round(elapsed_ms, 2),
                healthy=False,
                detail=str(exc),
            )
