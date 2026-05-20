"""
service.py

Main service interface for app deployment.

Orchestrates:
  1. Distributor - map nodes to VMs
  2. RuntimeGenerator - create _aether_main.py
  3. AppDeployer - SSH/SCP/pip to each VM
  4. ProcessManager - systemd unit generation and launching
  5. App health registration - auto-register deployed processes

This is the public API that the platform (gateway, orchestrators)
calls when deploying an app.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from urllib import error, request

from .distributor import Distributor
from .deployer import AppDeployer, SSHConnection
from .process_manager import ProcessManager, ServiceConfig
from .runtime_generator import RuntimeGenerator
from .models import DeploymentRecord, DeploymentStatus, ProcessRecord, ProcessStatus
from aether.kafka import topics

logger = logging.getLogger("aether.deployer.service")


class AppDeployerService:
    """
    Main service for deploying Aether applications.

    Public methods:
      - deploy(app_id, app_version, zip_path, config_path, vm_pool_path)
      - rollback(deployment_record)
      - start(deployment_record)
      - stop(deployment_record)
      - status(deployment_record)
    """

    def __init__(
        self,
        runtime_generator: Optional[RuntimeGenerator] = None,
        distributor: Optional[Distributor] = None,
        app_health_checker_base_url: Optional[str] = None,
        lifecycle_manager_base_url: Optional[str] = None,
    ):
        """Initialize service with optional dependency injection."""
        self.runtime_generator = runtime_generator or RuntimeGenerator()
        self.distributor = distributor or Distributor()
        self.app_health_checker_base_url = (
            app_health_checker_base_url
            or os.getenv("AETHER_APP_HEALTH_CHECKER_URL", "http://localhost:8015")
        ).rstrip("/")
        self.lifecycle_manager_base_url = (
            lifecycle_manager_base_url
            or os.getenv("AETHER_LIFECYCLE_MANAGER_URL", "http://localhost:8016")
        ).rstrip("/")
        self.kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self._kafka_producer = None
        self._init_kafka_producer()

    def deploy(
        self,
        app_id: str,
        app_version: str,
        zip_path: Path,
        config_path: Path,
        vm_pool_path: Optional[Path] = None,
        ssh_key: Optional[Path] = None,
        ssh_user: str = "ubuntu",
    ) -> DeploymentRecord:
        logger.info("=" * 70)
        logger.info("Starting deployment: %s v%s", app_id, app_version)
        logger.info("=" * 70)

        deployment = DeploymentRecord(
            app_id=app_id,
            app_version=app_version,
            status=DeploymentStatus.IN_PROGRESS,
        )

        try:
            logger.info("Step 1: Distributing nodes across VMs...")
            distribution = self.distributor.distribute(config_path, vm_pool_path)
            nodes = distribution.get("nodes", [])

            if not nodes:
                raise RuntimeError("No distribution nodes found in config.yaml")

            nodes_by_vm = self._group_nodes_by_vm(nodes)
            logger.info("Deploying to %s VMs", len(nodes_by_vm))

            for vm_ip, vm_nodes in nodes_by_vm.items():
                logger.info("Deploying to VM: %s", vm_ip)
                self._deploy_to_vm(
                    vm_ip=vm_ip,
                    app_id=app_id,
                    app_version=app_version,
                    zip_path=zip_path,
                    config_path=config_path,
                    nodes=vm_nodes,
                    deployment=deployment,
                    ssh_key=ssh_key,
                    ssh_user=ssh_user,
                )
            self._register_deployment_with_health_checker(deployment)
            self._register_deployment_with_lifecycle_manager(deployment)
            self._publish_deployed_event(deployment)

            deployment.status = DeploymentStatus.SUCCEEDED
            logger.info("Deployment succeeded")

        except Exception as exc:
            logger.error("Deployment failed: %s", exc)
            deployment.status = DeploymentStatus.FAILED
            deployment.error_message = str(exc)
            self._publish_event(
                topics.APP_LIFECYCLE,
                {
                    "event_type": "deployment.failed",
                    "app_id": app_id,
                    "app_version": app_version,
                    "detail": str(exc),
                },
            )
            raise

        return deployment

    def _register_deployment_with_health_checker(self, deployment: DeploymentRecord) -> None:
        endpoint = f"{self.app_health_checker_base_url}/health/targets"

        for process in deployment.process_records:
            payload = {
                "app_id": process.app_id,
                "app_version": process.app_version,
                "artifact_id": process.artifact_id,
                "vm_ip": process.vm_ip,
                "port": process.port,
                "health_path": "/health",
                "failure_threshold": 3,
            }

            data = json.dumps(payload).encode("utf-8")
            req = request.Request(
                endpoint,
                data=data,
                method="POST",
                headers={"Content-Type": "application/json"},
            )

            try:
                with request.urlopen(req, timeout=3.0) as response:
                    status = response.getcode()
                if status not in (200, 201):
                    logger.warning(
                        "Health registration unexpected status for %s: %s",
                        process.artifact_id,
                        status,
                    )
                else:
                    logger.info(
                        "Registered with app health checker: %s@%s:%s",
                        process.artifact_id,
                        process.vm_ip,
                        process.port,
                    )
            except error.URLError as exc:
                logger.warning(
                    "Unable to register process with app health checker (%s): %s",
                    process.artifact_id,
                    exc,
                )

    def _register_deployment_with_lifecycle_manager(self, deployment: DeploymentRecord) -> None:
        endpoint = f"{self.lifecycle_manager_base_url}/apps/{deployment.app_id}/register"
        payload = {
            "app_id": deployment.app_id,
            "app_version": deployment.app_version,
            "process_records": [p.to_dict() for p in deployment.process_records],
        }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            endpoint,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=3.0):
                logger.info("Registered deployment with lifecycle manager: %s", deployment.app_id)
        except error.URLError as exc:
            logger.warning("Unable to register with lifecycle manager (%s): %s", deployment.app_id, exc)

    def _init_kafka_producer(self) -> None:
        try:
            from kafka import KafkaProducer  # type: ignore

            self._kafka_producer = KafkaProducer(
                bootstrap_servers=self.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                request_timeout_ms=5000,
            )
            logger.info("Kafka producer connected: %s", self.kafka_bootstrap_servers)
        except Exception as exc:
            self._kafka_producer = None
            logger.warning("Kafka unavailable in deployer (%s). Events will be skipped.", exc)

    def _publish_event(self, topic: str, payload: dict) -> None:
        if not self._kafka_producer:
            return
        try:
            self._kafka_producer.send(topic, payload)
        except Exception as exc:
            logger.warning("Failed to publish event %s: %s", topic, exc)

    def _publish_deployed_event(self, deployment: DeploymentRecord) -> None:
        self._publish_event(
            topics.APP_DEPLOYED,
            {
                "event_type": "app.deployed",
                "app_id": deployment.app_id,
                "app_version": deployment.app_version,
                "deployment": deployment.to_dict(),
            },
        )

    def _group_nodes_by_vm(self, nodes: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        grouped = {}
        for node in nodes:
            vm_ip = node.get("vm_ip", "localhost")
            if vm_ip not in grouped:
                grouped[vm_ip] = []
            grouped[vm_ip].append(node)
        return grouped

    def _deploy_to_vm(
        self,
        vm_ip: str,
        app_id: str,
        app_version: str,
        zip_path: Path,
        config_path: Path,
        nodes: List[Dict[str, Any]],
        deployment: DeploymentRecord,
        ssh_key: Optional[Path] = None,
        ssh_user: str = "ubuntu",
    ) -> None:
        vm_user = nodes[0].get("vm_user", ssh_user) if nodes else ssh_user
        vm_password = nodes[0].get("vm_password") if nodes else None
        vm_port = int(nodes[0].get("vm_port", 22)) if nodes else 22
        vm_ssh_key = nodes[0].get("vm_ssh_key") if nodes else None

        resolved_key = vm_ssh_key or (str(ssh_key) if ssh_key else None)

        logger.info("Connecting to %s:%s as %s...", vm_ip, vm_port, vm_user)

        ssh = SSHConnection(
            hostname=vm_ip,
            username=vm_user,
            password=vm_password,
            port=vm_port,
            key_filename=resolved_key,
        )
        ssh.connect()

        try:
            app_deployer = AppDeployer(ssh)
            app_deployer.deploy(app_id, app_version, zip_path, config_path)

            process_manager = ProcessManager(ssh)

            for node in nodes:
                logger.info("Starting processes for node: %s", node.get("node_id"))

                artifacts = node.get("artifacts", [])
                role = node.get("role", "")
                port = node.get("port", 8000)

                for artifact_id in artifacts:
                    config = ServiceConfig(
                        app_id=app_id,
                        app_version=app_version,
                        artifact_id=artifact_id,
                        artifact_type=role,
                        port=port,
                        vm_ip=vm_ip,
                    )

                    process_manager.start_process(config, wait_for_ready=True)

                    process_rec = ProcessRecord(
                        app_id=app_id,
                        app_version=app_version,
                        artifact_id=artifact_id,
                        artifact_type=role,
                        vm_ip=vm_ip,
                        port=port,
                        systemd_service=config.service_name,
                        status=ProcessStatus.RUNNING,
                    )
                    deployment.process_records.append(process_rec)

        finally:
            ssh.close()

    def status(self, deployment: DeploymentRecord) -> Dict[str, Any]:
        return {
            "deployment_id": deployment.deployment_id,
            "app_id": deployment.app_id,
            "status": deployment.status.value,
            "process_count": len(deployment.process_records),
            "processes": [p.to_dict() for p in deployment.process_records],
        }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Deploy an Aether application")
    parser.add_argument("--app-id", required=True, help="App ID")
    parser.add_argument("--app-version", required=True, help="Version")
    parser.add_argument("--zip", type=Path, required=True, help="Path to app.zip")
    parser.add_argument("--config", type=Path, required=True, help="Path to config.yaml")
    parser.add_argument("--vm-pool", type=Path, help="Path to vm_pool.json")
    parser.add_argument("--key", type=Path, help="SSH private key")
    parser.add_argument("--user", default="ubuntu", help="SSH user")
    parser.add_argument("--health-checker-url", default=None, help="Base URL for app health checker")
    parser.add_argument("--lifecycle-url", default=None, help="Base URL for lifecycle manager")
    parser.add_argument("--output", type=Path, help="Save deployment record to JSON")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    service = AppDeployerService(
        app_health_checker_base_url=args.health_checker_url,
        lifecycle_manager_base_url=args.lifecycle_url,
    )
    deployment = service.deploy(
        app_id=args.app_id,
        app_version=args.app_version,
        zip_path=args.zip,
        config_path=args.config,
        vm_pool_path=args.vm_pool,
        ssh_key=args.key,
        ssh_user=args.user,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(deployment.to_dict(), handle, indent=2)
        logger.info("Saved deployment record to %s", args.output)
    else:
        print(json.dumps(deployment.to_dict(), indent=2))

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
