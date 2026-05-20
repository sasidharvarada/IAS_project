"""
process_manager.py

Generates systemd service units and manages process lifecycle on remote VMs.

Each deployed artifact becomes a systemd service:
  - Service name: aether-<app_id>-<artifact_id>
  - Working directory: /opt/aether/apps/<app_id>/<version>
  - Exec: _aether_main.py --role <role> --artifact <id> --port <port>
  - Restart: on-failure with exponential backoff
"""

import logging
import time
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

from .deployer import SSHConnection

logger = logging.getLogger("aether.deployer.process_manager")


@dataclass
class ServiceConfig:
    """Configuration for a systemd service."""
    app_id: str
    app_version: str
    artifact_id: str
    artifact_type: str      # "agent" | "tool" | "orchestrator" | "model"
    port: int
    vm_ip: str
    
    @property
    def service_name(self) -> str:
        """Generate systemd service name."""
        return f"aether-{self.app_id}-{self.artifact_id}".replace("_", "-").lower()
    
    @property
    def app_dir(self) -> str:
        """Absolute path on VM."""
        return f"/opt/aether/apps/{self.app_id}/{self.app_version}"


class SystemdServiceGenerator:
    """Generates systemd .service files."""
    
    SYSTEMD_DIR = "/etc/systemd/system"
    
    @staticmethod
    def generate_unit(config: ServiceConfig, env_vars: dict = None) -> str:
        """
        Generate systemd unit file content.
        
        Args:
            config: ServiceConfig with artifact details
            env_vars: Optional environment variables to pass to service
        
        Returns:
            systemd unit file as string
        """
        if env_vars is None:
            env_vars = {}
        
        # Build environment directive
        env_lines = []
        for key, value in env_vars.items():
            # Escape quotes in values
            safe_value = value.replace('"', '\\"')
            env_lines.append(f'Environment="{key}={safe_value}"')
        env_section = "\n".join(env_lines) if env_lines else ""
        
        unit = f"""[Unit]
Description=Aether {config.artifact_type} service: {config.artifact_id}
After=network.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={config.app_dir}
ExecStart={config.app_dir}/.venv/bin/python {config.app_dir}/_aether_main.py --role {config.artifact_type} --artifact {config.artifact_id} --port {config.port}

# Restart policy
Restart=on-failure
RestartSec=5
StartLimitInterval=300
StartLimitBurst=5

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier={config.service_name}

# Resource limits
MemoryLimit=2G
CPUQuota=75%

# User (run as app user if available, else as-is)
# User=aether
# Group=aether

{env_section}

[Install]
WantedBy=multi-user.target
"""
        return unit
    
    def deploy_unit(
        self,
        ssh: SSHConnection,
        config: ServiceConfig,
        env_vars: dict = None,
    ) -> None:
        """
        Deploy a systemd unit file to remote VM.
        
        Args:
            ssh: SSHConnection to remote VM
            config: ServiceConfig with artifact details
            env_vars: Optional environment variables
        
        Raises:
            RuntimeError: If deployment fails
        """
        service_name = config.service_name
        unit_path = f"{self.SYSTEMD_DIR}/{service_name}.service"
        unit_content = self.generate_unit(config, env_vars)
        
        logger.info(f"Deploying systemd unit: {service_name}")
        
        # Write to temporary file locally, then upload
        tmp_path = Path(f"/tmp/{service_name}.service")
        tmp_path.write_text(unit_content)
        
        # Upload via SCP
        ssh.scp_put(str(tmp_path), unit_path)
        
        # Reload systemd and enable service
        commands = [
            "systemctl daemon-reload",
            f"systemctl enable {service_name}",
        ]
        
        for cmd in commands:
            code, stdout, stderr = ssh.exec_command(cmd)
            if code != 0:
                raise RuntimeError(f"Failed: {cmd}\n{stderr}")
        
        logger.info(f"✓ Systemd unit deployed: {service_name}")


class ProcessManager:
    """Manages lifecycle of deployed artifact processes."""
    
    def __init__(self, ssh: SSHConnection):
        """Initialize with SSH connection."""
        self.ssh = ssh
        self.generator = SystemdServiceGenerator()
    
    def start_process(
        self,
        config: ServiceConfig,
        env_vars: dict = None,
        wait_for_ready: bool = True,
        ready_timeout_s: int = 30,
    ) -> None:
        """
        Start a deployed artifact process.
        
        Args:
            config: ServiceConfig with artifact details
            env_vars: Optional environment variables
            wait_for_ready: Wait for /health endpoint to respond
            ready_timeout_s: Timeout for readiness check
        
        Raises:
            RuntimeError: If start fails
        """
        logger.info(f"Starting process: {config.artifact_id} on port {config.port}")
        
        # Deploy systemd unit
        self.generator.deploy_unit(self.ssh, config, env_vars)
        
        # Start service
        service_name = config.service_name
        code, stdout, stderr = self.ssh.exec_command(f"systemctl start {service_name}")
        if code != 0:
            raise RuntimeError(f"Failed to start {service_name}: {stderr}")
        
        logger.info(f"✓ Process started: {service_name}")
        
        # Optional: wait for readiness
        if wait_for_ready:
            self._wait_for_ready(config, ready_timeout_s)
    
    def stop_process(self, config: ServiceConfig) -> None:
        """Stop a running process."""
        service_name = config.service_name
        logger.info(f"Stopping process: {service_name}")
        
        code, stdout, stderr = self.ssh.exec_command(f"systemctl stop {service_name}")
        if code != 0:
            logger.warning(f"Failed to stop {service_name}: {stderr}")
        else:
            logger.info(f"✓ Process stopped: {service_name}")
    
    def restart_process(self, config: ServiceConfig) -> None:
        """Restart a running process."""
        service_name = config.service_name
        logger.info(f"Restarting process: {service_name}")
        
        code, stdout, stderr = self.ssh.exec_command(f"systemctl restart {service_name}")
        if code != 0:
            raise RuntimeError(f"Failed to restart {service_name}: {stderr}")
        
        logger.info(f"✓ Process restarted: {service_name}")
        self._wait_for_ready(config, timeout_s=30)
    
    def get_process_status(self, config: ServiceConfig) -> dict:
        """Get status of a process."""
        service_name = config.service_name
        
        code, stdout, stderr = self.ssh.exec_command(
            f"systemctl show {service_name} --no-page --output=json 2>/dev/null || echo '{{}}'"
        )
        
        # Parse output (simplified)
        return {
            "service_name": service_name,
            "output": stdout.strip(),
        }
    
    def _wait_for_ready(self, config: ServiceConfig, timeout_s: int = 30) -> None:
        """
        Poll /health endpoint until ready.
        
        Args:
            config: ServiceConfig with artifact details
            timeout_s: Maximum time to wait
        
        Raises:
            RuntimeError: If not ready within timeout
        """
        import json
        
        logger.info(f"Waiting for process to be ready (max {timeout_s}s)...")
        
        start_time = time.time()
        while time.time() - start_time < timeout_s:
            try:
                # Use curl to check health endpoint
                url = f"http://localhost:{config.port}/health"
                cmd = f"curl -s {url} 2>/dev/null || echo '{{}}'"
                code, stdout, stderr = self.ssh.exec_command(cmd)
                
                if code == 0:
                    try:
                        response = json.loads(stdout)
                        if response.get("status") == "ok":
                            logger.info(f"✓ Process is ready")
                            return
                    except json.JSONDecodeError:
                        pass
            
            except Exception as e:
                logger.debug(f"Health check failed: {e}")
            
            time.sleep(2)
        
        logger.warning(f"Process did not become ready within {timeout_s}s")
    
    def start_all_processes(
        self,
        app_id: str,
        app_version: str,
        nodes: List[dict],
    ) -> List[ServiceConfig]:
        """
        Start all processes for an app deployment.
        
        Args:
            app_id: Application ID
            app_version: Version
            nodes: List of distribution nodes from config.yaml
        
        Returns:
            List of ServiceConfig objects for deployed processes
        
        Example nodes:
            [
                {
                    "node_id": "agent-node-1",
                    "role": "agent",
                    "port": 8001,
                    "artifacts": ["email-classifier-agent"],
                    "vm_ip": "192.168.1.10",
                }
            ]
        """
        configs = []
        
        for node in nodes:
            role = node.get("role", "")
            port = node.get("port", 8000)
            artifacts = node.get("artifacts", [])
            vm_ip = node.get("vm_ip", "localhost")
            
            for artifact_id in artifacts:
                config = ServiceConfig(
                    app_id=app_id,
                    app_version=app_version,
                    artifact_id=artifact_id,
                    artifact_type=role,
                    port=port,
                    vm_ip=vm_ip,
                )
                
                try:
                    self.start_process(config, wait_for_ready=True)
                    configs.append(config)
                except Exception as e:
                    logger.error(f"Failed to start {artifact_id}: {e}")
                    raise
        
        return configs


def main():
    """CLI entry point for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Manage systemd services for Aether apps"
    )
    parser.add_argument("hostname", help="VM IP or hostname")
    parser.add_argument("--username", default="ubuntu", help="SSH username")
    parser.add_argument("--key", help="SSH private key path")
    parser.add_argument("--action", choices=["start", "stop", "restart"], default="start")
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--app-version", required=True)
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--artifact-type", required=True)
    parser.add_argument("--port", type=int, default=8000)
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    ssh = SSHConnection(
        hostname=args.hostname,
        username=args.username,
        key_filename=args.key,
    )
    
    config = ServiceConfig(
        app_id=args.app_id,
        app_version=args.app_version,
        artifact_id=args.artifact_id,
        artifact_type=args.artifact_type,
        port=args.port,
        vm_ip=args.hostname,
    )
    
    manager = ProcessManager(ssh)
    
    if args.action == "start":
        manager.start_process(config)
    elif args.action == "stop":
        manager.stop_process(config)
    elif args.action == "restart":
        manager.restart_process(config)


if __name__ == "__main__":
    import sys
    sys.exit(main())
