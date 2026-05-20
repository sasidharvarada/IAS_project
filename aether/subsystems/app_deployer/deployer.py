"""
deployer.py

Handles SSH, SCP, and pip installation on remote VMs.

Responsibilities:
  1. SCP app ZIP to VM at /opt/aether/apps/<app_id>/
  2. Unzip the app
  3. Create Python virtualenv
  4. Run pip install -r requirements.txt
  5. Generate _aether_main.py (via runtime_generator)
"""

import subprocess
import logging
import time
from pathlib import Path
from typing import Optional, Tuple
import paramiko

logger = logging.getLogger("aether.deployer.deployer")


class SSHConnection:
    """
    Lightweight wrapper around Paramiko SSH client.
    Handles connection pooling and command execution.
    """
    
    def __init__(
        self,
        hostname: str,
        username: str,
        port: int = 22,
        password: Optional[str] = None,
        key_filename: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        Initialize SSH connection parameters.
        
        Args:
            hostname: VM IP or hostname
            username: SSH user (e.g., ubuntu, ec2-user)
            port: SSH port (default 22)
            password: SSH password (if using password auth)
            key_filename: Path to private key (if using key auth)
            timeout: Connection timeout in seconds
        """
        self.hostname = hostname
        self.username = username
        self.port = port
        self.password = password
        self.key_filename = key_filename
        self.timeout = timeout
        self.client: Optional[paramiko.SSHClient] = None
    
    def connect(self) -> None:
        """Establish SSH connection."""
        if self.client and self.client.get_transport() and self.client.get_transport().is_active():
            logger.debug(f"SSH connection already active to {self.hostname}")
            return
        
        logger.info(f"Connecting to {self.hostname}:{self.port} as {self.username}")
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            self.client.connect(
                hostname=self.hostname,
                port=self.port,
                username=self.username,
                password=self.password,
                key_filename=self.key_filename,
                timeout=self.timeout,
            )
            logger.info(f"✓ Connected to {self.hostname}")
        except Exception as e:
            logger.error(f"✗ SSH connection failed: {e}")
            raise
    
    def exec_command(self, command: str) -> Tuple[int, str, str]:
        """
        Execute command remotely and return exit code, stdout, stderr.
        
        Args:
            command: Shell command to execute
        
        Returns:
            (exit_code, stdout, stderr)
        """
        if not self.client:
            self.connect()
        
        logger.debug(f"Executing: {command}")
        stdin, stdout, stderr = self.client.exec_command(command)
        
        stdout_text = stdout.read().decode("utf-8", errors="replace")
        stderr_text = stderr.read().decode("utf-8", errors="replace")
        exit_code = stdout.channel.recv_exit_status()
        
        if exit_code != 0:
            logger.warning(f"Command exited with code {exit_code}")
            if stderr_text:
                logger.warning(f"stderr: {stderr_text[:200]}")
        
        return exit_code, stdout_text, stderr_text
    
    def scp_put(self, local_path: str, remote_path: str) -> None:
        """
        Upload a file via SCP.
        
        Args:
            local_path: Local file path
            remote_path: Remote file path
        """
        if not self.client:
            self.connect()
        
        logger.info(f"Uploading {local_path} → {self.hostname}:{remote_path}")
        
        sftp = self.client.open_sftp()
        try:
            # Ensure remote directory exists
            remote_dir = remote_path.rsplit("/", 1)[0]
            try:
                sftp.stat(remote_dir)
            except IOError:
                # Directory doesn't exist, create it
                self._mkdir_recursive(sftp, remote_dir)
            
            # Upload file
            sftp.put(local_path, remote_path)
            logger.info(f"✓ Uploaded {remote_path}")
        finally:
            sftp.close()
    
    def _mkdir_recursive(self, sftp, path: str) -> None:
        """Recursively create directories via SFTP."""
        if path == "/":
            return
        try:
            sftp.stat(path)
        except IOError:
            self._mkdir_recursive(sftp, path.rsplit("/", 1)[0])
            sftp.mkdir(path)
    
    def close(self) -> None:
        """Close SSH connection."""
        if self.client:
            self.client.close()
            logger.debug(f"SSH connection closed: {self.hostname}")


class AppDeployer:
    """
    Orchestrates deployment of an app to a remote VM.
    
    Workflow:
      1. Copy app ZIP to /opt/aether/apps/<app_id>/
      2. Unzip
      3. Create virtualenv
      4. pip install -r requirements.txt
      5. Generate _aether_main.py
    """
    
    AETHER_APPS_DIR = "/opt/aether/apps"
    
    def __init__(
        self,
        ssh_conn: SSHConnection,
    ):
        """
        Initialize deployer with SSH connection.
        
        Args:
            ssh_conn: SSHConnection instance
        """
        self.ssh = ssh_conn
    
    def deploy(
        self,
        app_id: str,
        app_version: str,
        zip_path: Path,
        config_path: Path,
    ) -> None:
        """
        Deploy app to remote VM.
        
        Args:
            app_id: Application ID (e.g., "email-classifier-agent")
            app_version: Version (e.g., "1.0.0")
            zip_path: Local path to app ZIP
            config_path: Local path to config.yaml
        
        Raises:
            RuntimeError: If any deployment step fails
        """
        logger.info(f"=" * 60)
        logger.info(f"Deploying {app_id} v{app_version} to {self.ssh.hostname}")
        logger.info(f"=" * 60)
        
        try:
            self.ssh.connect()
            
            # Step 1: Create app directory
            self._create_app_dir(app_id, app_version)
            
            # Step 2: Upload ZIP
            self._upload_zip(zip_path, app_id, app_version)
            
            # Step 3: Unzip
            self._unzip_app(app_id, app_version)
            
            # Step 4: Create virtualenv
            self._create_virtualenv(app_id, app_version)
            
            # Step 5: Install dependencies
            self._pip_install(app_id, app_version)
            
            # Step 6: Generate runtime
            self._generate_runtime(app_id, app_version, config_path)
            
            logger.info(f"✓ Deployment of {app_id} v{app_version} succeeded")
        
        except Exception as e:
            logger.error(f"✗ Deployment failed: {e}")
            raise
    
    def _create_app_dir(self, app_id: str, app_version: str) -> None:
        """Create app directory on VM."""
        app_dir = f"{self.AETHER_APPS_DIR}/{app_id}/{app_version}"
        logger.info(f"Creating app directory: {app_dir}")
        
        code, stdout, stderr = self.ssh.exec_command(f"mkdir -p {app_dir}")
        if code != 0:
            raise RuntimeError(f"Failed to create app directory: {stderr}")
        
        logger.info(f"✓ App directory created")
    
    def _upload_zip(self, zip_path: Path, app_id: str, app_version: str) -> None:
        """Upload app ZIP via SCP."""
        app_dir = f"{self.AETHER_APPS_DIR}/{app_id}/{app_version}"
        remote_zip = f"{app_dir}/app.zip"
        
        logger.info(f"Uploading ZIP: {zip_path}")
        self.ssh.scp_put(str(zip_path), remote_zip)
        logger.info(f"✓ ZIP uploaded")
    
    def _unzip_app(self, app_id: str, app_version: str) -> None:
        """Unzip app on VM."""
        app_dir = f"{self.AETHER_APPS_DIR}/{app_id}/{app_version}"
        remote_zip = f"{app_dir}/app.zip"
        
        logger.info(f"Unzipping app...")
        code, stdout, stderr = self.ssh.exec_command(
            f"cd {app_dir} && unzip -q app.zip && rm app.zip"
        )
        if code != 0:
            raise RuntimeError(f"Failed to unzip app: {stderr}")
        
        logger.info(f"✓ App unzipped")
    
    def _create_virtualenv(self, app_id: str, app_version: str) -> None:
        """Create Python virtualenv on VM."""
        app_dir = f"{self.AETHER_APPS_DIR}/{app_id}/{app_version}"
        venv_dir = f"{app_dir}/.venv"
        
        logger.info(f"Creating virtualenv...")
        code, stdout, stderr = self.ssh.exec_command(
            f"python3 -m venv {venv_dir}"
        )
        if code != 0:
            raise RuntimeError(f"Failed to create virtualenv: {stderr}")
        
        logger.info(f"✓ Virtualenv created")
    
    def _pip_install(self, app_id: str, app_version: str) -> None:
        """Install Python dependencies."""
        app_dir = f"{self.AETHER_APPS_DIR}/{app_id}/{app_version}"
        venv_bin = f"{app_dir}/.venv/bin"
        
        logger.info(f"Installing dependencies (pip install -r requirements.txt)...")
        code, stdout, stderr = self.ssh.exec_command(
            f"{venv_bin}/pip install -q -r {app_dir}/requirements.txt"
        )
        if code != 0:
            logger.error(f"pip install output:\n{stdout}")
            if stderr:
                logger.error(f"pip install errors:\n{stderr}")
            raise RuntimeError(f"Failed to install dependencies")
        
        logger.info(f"✓ Dependencies installed")
    
    def _generate_runtime(
        self,
        app_id: str,
        app_version: str,
        config_path: Path,
    ) -> None:
        """Generate _aether_main.py via runtime_generator."""
        from runtime_generator import RuntimeGenerator
        
        app_dir = f"{self.AETHER_APPS_DIR}/{app_id}/{app_version}"
        
        logger.info(f"Generating runtime...")
        
        # Note: this runs locally, then we SCP the result to VM
        gen = RuntimeGenerator()
        output_path = Path(f"/tmp/aether_main_{app_id}_{app_version}.py")
        
        gen.generate_runtime(config_path, output_path)
        
        # Upload generated file
        remote_main = f"{app_dir}/_aether_main.py"
        self.ssh.scp_put(str(output_path), remote_main)
        
        logger.info(f"✓ Runtime generated and deployed")


def main():
    """CLI entry point for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Deploy an Aether app to a remote VM"
    )
    parser.add_argument("hostname", help="VM IP or hostname")
    parser.add_argument("--username", default="ubuntu", help="SSH username")
    parser.add_argument("--password", help="SSH password")
    parser.add_argument("--key", help="SSH private key path")
    parser.add_argument("--app-id", required=True, help="App ID")
    parser.add_argument("--app-version", required=True, help="App version")
    parser.add_argument("--zip", type=Path, required=True, help="Path to app.zip")
    parser.add_argument("--config", type=Path, required=True, help="Path to config.yaml")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    ssh = SSHConnection(
        hostname=args.hostname,
        username=args.username,
        password=args.password,
        key_filename=args.key,
    )
    
    deployer = AppDeployer(ssh)
    deployer.deploy(args.app_id, args.app_version, args.zip, args.config)
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
