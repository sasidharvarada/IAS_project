"""
aether/subsystems/app_deployer

Orchestrates deployment of Aether applications across a VM pool.

Subsystems:
  - RuntimeGenerator: Generates _aether_main.py from config.yaml
  - Distributor: Maps distribution nodes to available VMs
  - AppDeployer: SSH/SCP/pip installation
  - ProcessManager: Systemd service generation and launching
  - RollbackManager: Stub for restoring previous app versions
  - AppDeployerService: Main orchestration service

Public API:
  from aether.subsystems.app_deployer import AppDeployerService
  
  service = AppDeployerService()
  deployment = service.deploy(
      app_id="email-classifier-agent",
      app_version="1.0.0",
      zip_path=Path("app.zip"),
      config_path=Path("config.yaml"),
  )
  print(deployment.to_dict())
"""

from .models import (
    DeploymentRecord,
    DeploymentStatus,
    ProcessRecord,
    ProcessStatus,
    DistributionNode,
    DeploymentStep,
)
from .runtime_generator import RuntimeGenerator
from .distributor import Distributor
from .deployer import AppDeployer, SSHConnection
from .process_manager import ProcessManager, SystemdServiceGenerator, ServiceConfig
from .rollback import RollbackManager, RollbackRequest
from .service import AppDeployerService

__all__ = [
    # Models
    "DeploymentRecord",
    "DeploymentStatus",
    "ProcessRecord",
    "ProcessStatus",
    "DistributionNode",
    "DeploymentStep",
    "ServiceConfig",
    # Services
    "RuntimeGenerator",
    "Distributor",
    "AppDeployer",
    "SSHConnection",
    "ProcessManager",
    "SystemdServiceGenerator",
    "RollbackManager",
    "RollbackRequest",
    "AppDeployerService",
]
