"""
models.py — Data classes for app deployment records and state.

Tracks:
  - Deployment records (which app version deployed to which VMs)
  - Process information (PID, port, VM, role)
  - Deployment status (pending, in-progress, succeeded, failed)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time
import uuid


class DeploymentStatus(str, Enum):
    """Lifecycle of a deployment."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class ProcessStatus(str, Enum):
    """Status of a running artifact process."""
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    CRASHED = "crashed"
    UNHEALTHY = "unhealthy"


@dataclass
class ProcessRecord:
    """
    Represents a deployed artifact instance (one process on one VM).
    
    Created after successfully launching a process via systemd on a remote VM.
    Tracks enough info to health-check, restart, or kill the process.
    """
    process_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    app_id: str = ""
    app_version: str = ""
    
    # Artifact identity
    artifact_id: str = ""        # e.g. "email-classifier-agent" or "text-simplifier"
    artifact_type: str = ""      # "agent" | "tool" | "orchestrator" | "model"
    
    # VM/Network
    vm_ip: str = ""              # e.g. "192.168.1.10"
    vm_name: str = ""            # e.g. "vm-node-2"
    port: int = 0                # e.g. 8001
    
    # Process identity
    pid: Optional[int] = None    # PID on the remote VM (may be 0 if not captured)
    systemd_service: str = ""    # e.g. "aether-app-email-classifier-agent"
    
    # Timestamps & status
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    stopped_at: Optional[float] = None
    status: ProcessStatus = ProcessStatus.STARTING
    
    # Health check tracking
    last_health_check: Optional[float] = None
    health_check_failures: int = 0
    
    # Error tracking
    error_message: str = ""
    
    def to_dict(self) -> dict:
        return {
            "process_id": self.process_id,
            "app_id": self.app_id,
            "app_version": self.app_version,
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "vm_ip": self.vm_ip,
            "vm_name": self.vm_name,
            "port": self.port,
            "pid": self.pid,
            "systemd_service": self.systemd_service,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "status": self.status.value,
            "last_health_check": self.last_health_check,
            "health_check_failures": self.health_check_failures,
            "error_message": self.error_message,
        }


@dataclass
class DeploymentRecord:
    """
    Top-level deployment record: one app version deployed across VMs.
    
    Deployment is atomic per app-version: either all nodes succeed or the
    whole thing is rolled back. Tracks which processes belong to this deployment.
    """
    deployment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    app_id: str = ""
    app_version: str = ""
    
    # Deployment config snapshot
    distribution_mode: str = ""  # "local" | "distributed" | "containerized"
    
    # State
    status: DeploymentStatus = DeploymentStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Process tracking
    process_records: list[ProcessRecord] = field(default_factory=list)
    
    # Rollback info
    previous_version: Optional[str] = None    # version to roll back to if this fails
    
    # Error tracking
    error_message: str = ""
    
    def to_dict(self) -> dict:
        return {
            "deployment_id": self.deployment_id,
            "app_id": self.app_id,
            "app_version": self.app_version,
            "distribution_mode": self.distribution_mode,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "process_records": [p.to_dict() for p in self.process_records],
            "previous_version": self.previous_version,
            "error_message": self.error_message,
        }


@dataclass
class DistributionNode:
    """
    Parsed from config.yaml distribution.nodes[].
    
    Represents one logical process role: agent, tools, orchestrator, or model.
    Maps to actual VM at deployment time via VM pool lookup.
    """
    node_id: str = ""              # e.g. "agent-node-1"
    role: str = ""                 # "agent" | "tool" | "orchestrator" | "model"
    host: Optional[str] = None     # May be overridden at deploy time
    port: int = 0
    artifacts: list[str] = field(default_factory=list)  # artifact IDs to deploy here
    
    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "role": self.role,
            "host": self.host,
            "port": self.port,
            "artifacts": self.artifacts,
        }


@dataclass
class DeploymentStep:
    """
    Represents one unit of work in the deployment process.
    Used for progress tracking and rollback sequencing.
    """
    step_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    step_name: str = ""            # e.g. "copy_zip_to_vm_1", "pip_install_vm_2"
    status: DeploymentStatus = DeploymentStatus.PENDING
    error_message: str = ""
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    
    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "status": self.status.value,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }
