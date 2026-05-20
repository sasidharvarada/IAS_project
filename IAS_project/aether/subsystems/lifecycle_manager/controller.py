"""
controller.py

Lifecycle control state and operations for deployed apps.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from aether.kafka import topics
from aether.subsystems.app_deployer.models import DeploymentRecord, DeploymentStatus, ProcessRecord, ProcessStatus

logger = logging.getLogger("aether.lifecycle_manager.controller")


@dataclass
class LifecycleActionResult:
    app_id: str
    action: str
    status: str
    message: str

    def to_dict(self) -> dict:
        return {
            "app_id": self.app_id,
            "action": self.action,
            "status": self.status,
            "message": self.message,
        }


class LifecycleController:
    def __init__(self):
        self.deployments: Dict[str, DeploymentRecord] = {}
        self.notification_url = os.getenv("AETHER_NOTIFICATION_SERVICE_URL", "http://localhost:8019").rstrip("/")
        self.alert_email = os.getenv("AETHER_ALERT_EMAIL", "")
        self.kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        repo_root = Path(__file__).resolve().parents[3]
        self.state_path = Path(
            os.getenv(
                "AETHER_LIFECYCLE_STATE_PATH",
                str(repo_root / ".run" / "storage" / "deployments.json"),
            )
        )
        self._kafka_producer = None
        self._init_kafka_producer()
        self._load_state()

    def register_deployment(self, deployment: DeploymentRecord) -> None:
        self.deployments[deployment.app_id] = deployment
        self._save_state()

    def register_deployment_dict(self, payload: dict) -> None:
        deployment = self._deployment_from_dict(payload)
        self.register_deployment(deployment)

    def unregister_deployment(self, app_id: str) -> bool:
        if app_id not in self.deployments:
            return False
        self.deployments.pop(app_id, None)
        self._save_state()
        return True

    def _process_from_dict(self, process: dict, app_id: str, app_version: str) -> ProcessRecord:
        return ProcessRecord(
            app_id=app_id,
            app_version=app_version,
            artifact_id=process.get("artifact_id", ""),
            artifact_type=process.get("artifact_type", ""),
            vm_ip=process.get("vm_ip", ""),
            vm_name=process.get("vm_name", ""),
            port=process.get("port", 0),
            pid=process.get("pid"),
            systemd_service=process.get("systemd_service", ""),
            created_at=process.get("created_at", 0.0),
            started_at=process.get("started_at"),
            stopped_at=process.get("stopped_at"),
            status=ProcessStatus(process.get("status", ProcessStatus.RUNNING.value)),
            last_health_check=process.get("last_health_check"),
            health_check_failures=process.get("health_check_failures", 0),
            error_message=process.get("error_message", ""),
        )

    def _deployment_from_dict(self, payload: dict) -> DeploymentRecord:
        deployment = DeploymentRecord(
            deployment_id=payload.get("deployment_id", ""),
            app_id=payload.get("app_id", ""),
            app_version=payload.get("app_version", ""),
            distribution_mode=payload.get("distribution_mode", ""),
            status=DeploymentStatus(payload.get("status", DeploymentStatus.PENDING.value)),
            created_at=payload.get("created_at", 0.0),
            started_at=payload.get("started_at"),
            completed_at=payload.get("completed_at"),
            previous_version=payload.get("previous_version"),
            error_message=payload.get("error_message", ""),
        )
        for process in payload.get("process_records", []):
            deployment.process_records.append(
                self._process_from_dict(process, deployment.app_id, deployment.app_version)
            )
        return deployment

    def _load_state(self) -> None:
        if not self.state_path.exists():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            for item in payload.get("deployments", []):
                deployment = self._deployment_from_dict(item)
                self.deployments[deployment.app_id] = deployment
            logger.info("Loaded %s lifecycle deployments from %s", len(self.deployments), self.state_path)
        except Exception as exc:
            logger.warning("Failed to load lifecycle state from %s: %s", self.state_path, exc)

    def _save_state(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"deployments": [deployment.to_dict() for deployment in self.deployments.values()]}
            self.state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to save lifecycle state to %s: %s", self.state_path, exc)

    def status(self, app_id: str) -> dict:
        deployment = self.deployments.get(app_id)
        if not deployment:
            return {
                "app_id": app_id,
                "registered": False,
                "message": "No deployment registered",
            }
        return {
            "app_id": deployment.app_id,
            "app_version": deployment.app_version,
            "registered": True,
            "process_count": len(deployment.process_records),
            "processes": [p.to_dict() for p in deployment.process_records],
        }

    def start(self, app_id: str, app_version: Optional[str] = None) -> LifecycleActionResult:
        deployment = self._require_deployment(app_id)
        for process in deployment.process_records:
            process.status = ProcessStatus.RUNNING
        self._save_state()
        return LifecycleActionResult(app_id, "start", "ok", f"Started {len(deployment.process_records)} processes")

    def stop(self, app_id: str, app_version: Optional[str] = None) -> LifecycleActionResult:
        deployment = self._require_deployment(app_id)
        for process in deployment.process_records:
            process.status = ProcessStatus.STOPPED
        self._save_state()
        return LifecycleActionResult(app_id, "stop", "ok", f"Stopped {len(deployment.process_records)} processes")

    def restart(self, app_id: str, app_version: Optional[str] = None, reason: str = "") -> LifecycleActionResult:
        deployment = self._require_deployment(app_id)
        for process in deployment.process_records:
            process.status = ProcessStatus.RUNNING
        message = f"Restarted {len(deployment.process_records)} processes"
        if reason:
            message = f"{message} (reason: {reason})"
        self._notify_event(
            event_type="app.restarted",
            app_id=deployment.app_id,
            app_version=app_version or deployment.app_version,
            detail=reason or "Automatic restart from lifecycle manager",
        )
        self._save_state()
        return LifecycleActionResult(app_id, "restart", "ok", message)

    def scale(self, app_id: str, replicas: int) -> LifecycleActionResult:
        deployment = self._require_deployment(app_id)
        current = len(deployment.process_records)

        if current == 0:
            return LifecycleActionResult(app_id, "scale", "ok", "No processes to scale")

        if replicas == current:
            return LifecycleActionResult(app_id, "scale", "ok", f"Already at replicas={replicas}")

        if replicas < current:
            deployment.process_records = deployment.process_records[:replicas]
            self._save_state()
            return LifecycleActionResult(app_id, "scale", "ok", f"Scaled down to replicas={replicas}")

        base = deployment.process_records[0]
        for idx in range(replicas - current):
            deployment.process_records.append(
                ProcessRecord(
                    app_id=base.app_id,
                    app_version=base.app_version,
                    artifact_id=base.artifact_id,
                    artifact_type=base.artifact_type,
                    vm_ip=base.vm_ip,
                    port=base.port + current + idx,
                    systemd_service=base.systemd_service,
                    status=ProcessStatus.RUNNING,
                )
            )

        self._save_state()
        return LifecycleActionResult(app_id, "scale", "ok", f"Scaled up to replicas={replicas}")

    def rollback(self, app_id: str, target_version: str) -> LifecycleActionResult:
        self._require_deployment(app_id)
        return LifecycleActionResult(app_id, "rollback", "ok", f"Rollback request accepted: target={target_version}")

    def _require_deployment(self, app_id: str) -> DeploymentRecord:
        deployment = self.deployments.get(app_id)
        if not deployment:
            raise ValueError(f"App '{app_id}' is not registered in lifecycle manager")
        return deployment

    def _notify_event(self, event_type: str, app_id: str, app_version: str, detail: str) -> None:
        self._publish_event(
            topics.APP_LIFECYCLE,
            {
                "event_type": event_type,
                "app_id": app_id,
                "app_version": app_version,
                "detail": detail,
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
        except Exception as exc:
            self._kafka_producer = None
            logger.warning("Kafka unavailable in lifecycle manager (%s).", exc)

    def _publish_event(self, topic: str, payload: dict) -> None:
        if not self._kafka_producer:
            return
        try:
            self._kafka_producer.send(topic, payload)
        except Exception as exc:
            logger.warning("Failed to publish lifecycle event: %s", exc)


controller = LifecycleController()