"""
models.py

Data models for app health monitoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass
class ProbeResult:
    app_id: str
    artifact_id: str
    vm_ip: str
    port: int
    checked_at: float = field(default_factory=time.time)
    response_time_ms: Optional[float] = None
    http_status: Optional[int] = None
    healthy: bool = False
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "app_id": self.app_id,
            "artifact_id": self.artifact_id,
            "vm_ip": self.vm_ip,
            "port": self.port,
            "checked_at": self.checked_at,
            "response_time_ms": self.response_time_ms,
            "http_status": self.http_status,
            "healthy": self.healthy,
            "detail": self.detail,
        }


@dataclass
class AppHealthRecord:
    app_id: str
    app_version: str
    artifact_id: str
    vm_ip: str
    port: int
    health_path: str = "/health"
    failure_threshold: int = 3
    status: HealthStatus = HealthStatus.UNKNOWN
    consecutive_failures: int = 0
    last_checked: Optional[float] = None
    last_healthy_at: Optional[float] = None
    last_error: str = ""
    last_http_status: Optional[int] = None
    last_response_time_ms: Optional[float] = None

    @property
    def endpoint(self) -> str:
        return f"http://{self.vm_ip}:{self.port}{self.health_path}"

    def apply_probe(self, probe: ProbeResult) -> None:
        self.last_checked = probe.checked_at
        self.last_http_status = probe.http_status
        self.last_response_time_ms = probe.response_time_ms

        if probe.healthy:
            self.consecutive_failures = 0
            self.last_error = ""
            self.last_healthy_at = probe.checked_at
            self.status = HealthStatus.HEALTHY
            return

        self.consecutive_failures += 1
        self.last_error = probe.detail

        if self.consecutive_failures >= self.failure_threshold:
            self.status = HealthStatus.DOWN
        else:
            self.status = HealthStatus.DEGRADED

    def to_dict(self) -> dict:
        return {
            "app_id": self.app_id,
            "app_version": self.app_version,
            "artifact_id": self.artifact_id,
            "vm_ip": self.vm_ip,
            "port": self.port,
            "health_path": self.health_path,
            "endpoint": self.endpoint,
            "failure_threshold": self.failure_threshold,
            "status": self.status.value,
            "consecutive_failures": self.consecutive_failures,
            "last_checked": self.last_checked,
            "last_healthy_at": self.last_healthy_at,
            "last_error": self.last_error,
            "last_http_status": self.last_http_status,
            "last_response_time_ms": self.last_response_time_ms,
        }
