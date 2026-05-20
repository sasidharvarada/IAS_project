# App Deployer Subsystem

The `app_deployer` subsystem orchestrates deployment of Aether applications across a pool of virtual machines. It handles:

1. **Runtime generation** — Transform `config.yaml` into executable FastAPI servers
2. **VM selection** — Distribute app nodes across the healthiest available VMs
3. **Remote deployment** — SSH/SCP/pip installation on target VMs
4. **Process management** — Generate systemd services and launch artifact processes
5. **Health monitoring** — Poll `/health` endpoints until ready

## Architecture

```
config.yaml
    ↓
Distributor (maps nodes → VMs)
    ↓
RuntimeGenerator (_aether_main.py)
    ↓
AppDeployer (SSH/SCP/pip)
    ↓
ProcessManager (systemd + launch)
    ↓
Running artifacts on VM pool
```

## Deployment Flow

### 1. Developer Writes App

```yaml
# config.yaml
app:
  name: email-classifier-agent
  version: "1.0.0"

artifacts:
  agents:
    - id: email-classifier-agent
      class: agents.email_classifier_agent.EmailClassifierAgent
  
  tools:
    - id: text-simplifier
      class: tools.text_simplifier.TextSimplifierTool
    - id: email-categorizer
      class: tools.email_categorizer.EmailCategorizerTool
    - id: priority-scorer
      class: tools.priority_scorer.PriorityScorerTool
  
  orchestrators:
    - id: email-pipeline-orchestrator
      class: orchestrators.email_pipeline.EmailPipelineOrchestrator
  
  models:
    - id: email-llm-model
      class: models.email_model.EmailLLMModel

distribution:
  mode: distributed
  nodes:
    - node_id: agent-node-1
      role: agent
      port: 8001
      artifacts:
        - email-classifier-agent
    
    - node_id: tool-node-1
      role: tools
      port: 8002
      artifacts:
        - text-simplifier
        - email-categorizer
        - priority-scorer
```

### 2. Developer Uploads ZIP

```
email-classifier-agent.zip
├── main.py              (CLI entry point, NOT server code)
├── config.yaml
├── requirements.txt
├── agents/
│   └── email_classifier_agent.py
├── tools/
│   ├── text_simplifier.py
│   ├── email_categorizer.py
│   └── priority_scorer.py
├── orchestrators/
│   └── email_pipeline.py
└── models/
    └── email_model.py
```

### 3. Platform Calls Deployer

```python
from aether.subsystems.app_deployer import AppDeployerService

service = AppDeployerService()
deployment = service.deploy(
    app_id="email-classifier-agent",
    app_version="1.0.0",
    zip_path=Path("apps/email-classifier-agent.zip"),
    config_path=Path("apps/email-classifier-agent/config.yaml"),
    vm_pool_path=Path("infra/vm_pool.json"),
    ssh_key=Path("~/.ssh/id_rsa"),
    ssh_user="ubuntu",
)

print(deployment.status)  # DeploymentStatus.SUCCEEDED
print(deployment.process_records)  # List of ProcessRecord
```

## Component Details

### RuntimeGenerator

**Input:** `config.yaml`  
**Output:** `_aether_main.py` (FastAPI wrapper)

Reads artifact declarations and generates a FastAPI server that:
- Accepts `--role (agent|tool|orchestrator|model)`
- Dynamically imports artifact classes
- Serves `/run` endpoint (POST) — executes artifact
- Serves `/health` endpoint (GET) — reports status

#### Usage

```bash
# Generate runtime from config.yaml
python -m aether.subsystems.app_deployer.runtime_generator \
    apps/email-classifier-agent/config.yaml \
    --output apps/email-classifier-agent/_aether_main.py
```

#### Generated Runtime Example

```python
# _aether_main.py (auto-generated from template)

@app.post("/run")
def run(body: dict):
    """Execute agent with given inputs."""
    response = agent.run(**body)
    return response.to_dict()

@app.get("/health")
def health():
    """Health check endpoint."""
    return agent.health()

# Boot as FastAPI server
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", required=True)       # agent | tool | orchestrator
    parser.add_argument("--artifact", required=False)  # artifact ID
    parser.add_argument("--port", type=int, default=8000)
    
    args = parser.parse_args()
    
    if args.role == "agent":
        boot_agent(args.artifact or DEFAULT_AGENT, args.port)
    elif args.role == "tool":
        boot_tool(args.artifact, args.port)
    # ... etc
```

### Distributor

**Input:** `config.yaml` + `vm_pool.json`  
**Output:** Augmented distribution config with VM IPs assigned

Reads `distribution.nodes` and maps each to a healthy VM from the pool.

#### VM Pool Schema

```json
{
  "vms": [
    {
      "name": "vm-1",
      "ip": "192.168.1.10",
      "roles": ["agent", "tool"],
      "status": "healthy",
      "cpu_pct": 25.0,
      "ram_pct": 60.0,
      "latency_ms": 2.5
    }
  ]
}
```

#### Usage

```python
from aether.subsystems.app_deployer import Distributor

distributor = Distributor()
distribution = distributor.distribute(
    config_path=Path("config.yaml"),
    vm_pool_path=Path("vm_pool.json"),
)

for node in distribution["nodes"]:
    print(f"{node['node_id']} → {node['vm_ip']}")
    # agent-node-1 → 192.168.1.10
    # tool-node-1 → 192.168.1.11
```

### AppDeployer

**Input:** App ZIP, Config, SSH credentials  
**Output:** Deployed app on remote VM ready for process launch

Handles SSH connection, SCP upload, unzip, virtualenv, and pip install.

#### Deployment Steps

1. Connect via SSH to VM
2. Create `/opt/aether/apps/<app_id>/<version>/` directory
3. SCP `app.zip` to remote
4. Unzip app
5. Create Python virtualenv (`.venv`)
6. Run `pip install -r requirements.txt`
7. Generate `_aether_main.py` (via RuntimeGenerator)

#### Usage

```python
from aether.subsystems.app_deployer import AppDeployer, SSHConnection

ssh = SSHConnection(
    hostname="192.168.1.10",
    username="ubuntu",
    key_filename="/home/user/.ssh/id_rsa",
)

deployer = AppDeployer(ssh)
deployer.deploy(
    app_id="email-classifier-agent",
    app_version="1.0.0",
    zip_path=Path("app.zip"),
    config_path=Path("config.yaml"),
)
```

### ProcessManager

**Input:** Service config, app location on VM  
**Output:** Running systemd services

Generates systemd `.service` files and launches processes via `systemctl`.

#### Generated Systemd Unit

```ini
# /etc/systemd/system/aether-email-classifier-agent.service

[Unit]
Description=Aether agent service: email-classifier-agent
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/aether/apps/email-classifier-agent/1.0.0
ExecStart=/opt/aether/apps/email-classifier-agent/1.0.0/.venv/bin/python \
    /opt/aether/apps/email-classifier-agent/1.0.0/_aether_main.py \
    --role agent \
    --artifact email-classifier-agent \
    --port 8001

Restart=on-failure
RestartSec=5
StartLimitInterval=300
StartLimitBurst=5

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### Usage

```python
from aether.subsystems.app_deployer import ProcessManager, ServiceConfig

ssh = SSHConnection("192.168.1.10", "ubuntu")

manager = ProcessManager(ssh)

config = ServiceConfig(
    app_id="email-classifier-agent",
    app_version="1.0.0",
    artifact_id="email-classifier-agent",
    artifact_type="agent",
    port=8001,
    vm_ip="192.168.1.10",
)

# Start process with health check
manager.start_process(config, wait_for_ready=True, ready_timeout_s=30)

# Check status
status = manager.get_process_status(config)

# Stop process
manager.stop_process(config)

# Restart
manager.restart_process(config)
```

### AppDeployerService (Main Orchestrator)

High-level API that orchestrates all components.

#### Usage

```python
from aether.subsystems.app_deployer import AppDeployerService
from pathlib import Path

service = AppDeployerService()

# Full deployment end-to-end
deployment = service.deploy(
    app_id="email-classifier-agent",
    app_version="1.0.0",
    zip_path=Path("dist/email-classifier-agent-1.0.0.zip"),
    config_path=Path("apps/email-classifier-agent/config.yaml"),
    vm_pool_path=Path("infra/vm_pool.json"),
    ssh_key=Path("~/.ssh/platform-key.pem"),
    ssh_user="ubuntu",
)

# Check deployment status
print(f"Status: {deployment.status.value}")  # "succeeded"
print(f"Deployed processes: {len(deployment.process_records)}")

for proc in deployment.process_records:
    print(f"  {proc.artifact_id}: {proc.vm_ip}:{proc.port} (systemd: {proc.systemd_service})")

# Get unified status
status_dict = service.status(deployment)
print(json.dumps(status_dict, indent=2))
```

## Data Models

### DeploymentRecord

Top-level record for one app deployment across multiple VMs.

```python
@dataclass
class DeploymentRecord:
    deployment_id: str                      # UUID
    app_id: str                             # e.g. "email-classifier-agent"
    app_version: str                        # e.g. "1.0.0"
    status: DeploymentStatus                # pending | in_progress | succeeded | failed
    process_records: list[ProcessRecord]    # List of running artifact processes
    error_message: str                      # Error details if failed
```

### ProcessRecord

Represents one deployed artifact instance (one process on one VM).

```python
@dataclass
class ProcessRecord:
    process_id: str                         # UUID
    app_id: str
    artifact_id: str                        # e.g. "text-simplifier"
    artifact_type: str                      # "agent" | "tool" | "orchestrator" | "model"
    vm_ip: str                              # "192.168.1.10"
    port: int                               # 8001
    systemd_service: str                    # "aether-email-classifier-agent"
    status: ProcessStatus                   # starting | running | stopped | crashed
    pid: Optional[int]                      # Process ID on remote VM
    error_message: str                      # Error if crashed
```

## Integration with Platform

### With App Registry

After deployment succeeds, the App Registry should record:
- App ZIP location: `/apps/<app_id>/<version>/source/`
- Deployment record: stored in PostgreSQL
- Process records: linked to deployment

### With VM Health Checker

The Distributor queries VM health to select nodes:
- Reads `vm_pool.json` (snapshot) OR
- Queries VM Health Checker subsystem via Kafka/HTTP for real-time health

### With Notification Service

After deployment, emit Kafka events:
- `app.deployed` — deployment succeeded
- `app.deployment_failed` — deployment failed
- Include process records for developer dashboard

## CLI Usage

### Runtime Generator

```bash
python -m aether.subsystems.app_deployer.runtime_generator \
    config.yaml \
    --output _aether_main.py
```

### Distributor

```bash
python -m aether.subsystems.app_deployer.distributor \
    config.yaml \
    --vm-pool vm_pool.json \
    --output augmented_config.json
```

### AppDeployer

```bash
python -m aether.subsystems.app_deployer.deployer \
    192.168.1.10 \
    --username ubuntu \
    --key ~/.ssh/id_rsa \
    --app-id email-classifier-agent \
    --app-version 1.0.0 \
    --zip app.zip \
    --config config.yaml
```

### ProcessManager

```bash
python -m aether.subsystems.app_deployer.process_manager \
    192.168.1.10 \
    --username ubuntu \
    --key ~/.ssh/id_rsa \
    --action start \
    --app-id email-classifier-agent \
    --app-version 1.0.0 \
    --artifact-id text-simplifier \
    --artifact-type tool \
    --port 8102
```

### Full Deployment Service

```bash
python -m aether.subsystems.app_deployer.service \
    --app-id email-classifier-agent \
    --app-version 1.0.0 \
    --zip dist/email-classifier-agent-1.0.0.zip \
    --config apps/email-classifier-agent/config.yaml \
    --vm-pool infra/vm_pool.json \
    --key ~/.ssh/platform-key.pem \
    --user ubuntu \
    --output deployment_record.json
```

## Error Handling

### SSH Connection Failures

If SSH connection fails:
1. Deployer logs error and raises `RuntimeError`
2. Deployment marked as `FAILED`
3. Error message: SSH error details
4. Caller should retry or rollback

### Dependency Installation Failures

If `pip install` fails:
1. Deployer logs pip output
2. Common issues:
   - Missing system dependencies (e.g., `build-essential`)
   - Network issues downloading packages
   - Incompatible Python versions
3. Deployment marked as `FAILED`
4. Error message: pip stderr

### Health Check Timeouts

If `/health` endpoint doesn't respond within timeout:
1. ProcessManager logs warning
2. Deployment continues (process may still start)
3. App Health Checker will pick it up later and report unhealthy
4. Lifecycle Manager can auto-restart if configured

## Future Enhancements

1. **Rollback** — `service.rollback(deployment)` to restore previous version
2. **Blue-Green Deployment** — Deploy alongside current version, switch traffic
3. **Canary Deployment** — Start on 1 VM, monitor, then expand
4. **Rolling Updates** — Restart processes one by one with health checks
5. **Secrets Management** — Inject credentials from vault into systemd units
6. **Container Support** — Generate Docker Compose files (Mode C: containerized)
7. **Monitoring** — Export deployment metrics to Prometheus

## Recent Changes

- **2026-05-06:** Fixed UTF-8 file write in `runtime_generator.py` to avoid Windows encoding errors (`open(..., encoding="utf-8")`). This resolves UnicodeEncodeError when generating `_aether_main.py` on Windows.
- **2026-05-06:** Fixed Jinja2 template variable names in `templates/_aether_main.py.j2` so generated imports and registries are populated correctly (use `artifact.module` / `artifact.classname`).
- **Validation:** Ran `runtime_generator` against `apps/email_classifier/config.yaml` — generated `_aether_main.py` passed `py_compile` and contains correct artifact imports and registries.

Quick usage to regenerate runtime (example):

```bash
python -m aether.subsystems.app_deployer.runtime_generator \
    apps/email_classifier/config.yaml \
    --output apps/email_classifier/_aether_main.py
```

If you want, I can also add an explicit changelog file or annotate the root README with these notes.
