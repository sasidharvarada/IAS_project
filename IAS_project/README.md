# AetherAgents Platform

A distributed, agentic AI application platform that deploys artifact-based AI applications (agents, tools, orchestrators, models) across a pool of virtual machines.

## Overview

AetherAgents is a **production-ready platform** for:

1. **Defining** AI applications as composable artifacts (agents, tools, models, orchestrators)
2. **Validating** app structure and configuration
3. **Distributing** app nodes across a VM pool
4. **Deploying** with automated SSH/SCP/systemd orchestration
5. **Monitoring** health and managing lifecycle

### Key Concepts

- **Artifacts** — Reusable AI components: Agents (top-level coordinators), Tools (microservices), Models (LLM wrappers), Orchestrators (pipelines)
- **Distribution** — Define which artifacts run where via `config.yaml`
- **Deployment Mode** — Choose local (single VM), distributed (artifact per process), or containerized (Docker)
- **Platform Subsystems** — Modular services for validation, registry, VM health, deployment, lifecycle management

## Project Structure

```
AetherAgents/
│
├── aether/                          # Platform codebase (production)
│   ├── core/                          # Base artifact classes
│   │   ├── base_agent.py              # Agent abstract base
│   │   ├── base_tool.py               # Tool abstract base
│   │   ├── base_orchestrator.py       # Orchestrator abstract base
│   │   ├── base_model.py              # Model abstract base
│   │   └── __init__.py
│   │
│   └── subsystems/                    # Standalone services (in progress)
│       ├── app_deployer/              # ✅ Deploy apps to VMs
│       │   ├── runtime_generator.py   # Generate _aether_main.py
│       │   ├── distributor.py         # Map nodes to VMs
│       │   ├── deployer.py            # SSH/SCP/pip orchestration
│       │   ├── process_manager.py     # Systemd service lifecycle
│       │   ├── rollback.py            # Rollback stub
│       │   ├── service.py             # Main orchestrator API
│       │   ├── models.py              # Data models
│       │   ├── templates/
│       │   │   └── _aether_main.py.j2 # FastAPI wrapper template
│       │   ├── README.md
│       │   └── requirements.txt
│       │
│       ├── cli_generator/             # ✅ Generate CLI usage docs
│       │   ├── generator.py           # Read config.yaml and render docs
│       │   ├── service.py             # CLI entry point
│       │   ├── templates/
│       │   │   └── cli_usage.md.j2    # Markdown template
│       │   ├── README.md
│       │   └── requirements.txt
│       │
│       ├── build_packager/            # ✅ Validate and package apps
│       │   ├── builder.py             # Syntax checks, dry-run deps, manifest
│       │   ├── service.py             # HTTP + CLI entry point
│       │   ├── README.md
│       │   └── requirements.txt
│       │
│       ├── (future subsystems)
│       │   ├── user_management/       # Register, login, API keys, RBAC
│       │   ├── app_validator/         # Validate structure & config
│       │   ├── app_registry/          # Store app versions & metadata
│       │   ├── vm_health_checker/     # Monitor VM health via SSH/HTTP
│       │   ├── app_health_checker/    # Monitor deployed app health
│       │   ├── lifecycle_manager/     # Start, stop, restart, scale
│       │   └── notification_service/  # Email, webhook, dashboard push
│       │
│       └── __init__.py
│
├── apps/                              # Deployed app artifacts
│   └── email_classifier/              # Example: Email Classifier Agent
│       ├── main.py                    # CLI entry point
│       ├── config.yaml                # Artifact definitions + distribution
│       ├── requirements.txt
│       ├── sample_email.txt
│       │
│       ├── agents/
│       │   └── email_classifier_agent.py
│       ├── tools/
│       │   ├── text_simplifier.py
│       │   ├── email_categorizer.py
│       │   └── priority_scorer.py
│       ├── orchestrators/
│       │   └── email_pipeline.py
│       ├── models/
│       │   └── email_model.py
│       └── README.md
│   └── study_planner/                 # Example: Study Planner Agent
│       ├── main.py                    # CLI entry point
│       ├── config.yaml                # Artifact definitions + distribution
│       ├── requirements.txt
│       ├── README.md
│       ├── agents/
│       │   └── study_planner_agent.py
│       ├── tools/
│       │   ├── goal_analyzer.py
│       │   └── session_planner.py
│       ├── orchestrators/
│       │   └── study_pipeline.py
│       └── models/
│           └── study_model.py
│
├── ARCHITECTURE.md                    # Full platform architecture spec
├── DEPLOYER.md                        # Deployment modes & runtime design
└── README.md                          # This file
```

## Platform Components

### Core Artifact Classes (`aether/core/`)

Base classes for all artifact types:

| Class | Purpose | Key Methods |
|-------|---------|------------|
| **BaseAgent** | Top-level coordinator | `run(**inputs) → AgentResponse` |
| **BaseTool** | Stateless microservice | `run(**inputs) → dict` |
| **BaseOrchestrator** | Multi-step pipeline | `run(**inputs) → dict` |
| **BaseModel** | LLM / embedding wrapper | `complete(prompt, ...) → str` |

All artifacts expose a `health()` method that returns status.

### Sample Application (`apps/email_classifier/`)

Complete, runnable email classification system demonstrating artifact composition:

**Architecture:**
```
EmailClassifierAgent (top-level)
    ├── EmailLLMModel (Gemini)
    └── EmailPipelineOrchestrator (sequential)
        ├── TextSimplifierTool (strips jargon)
        ├── EmailCategorizerTool (classifies)
        └── PriorityScorerTool (prioritizes)
```

**Usage:**
```bash
cd apps/email_classifier
pip install -r requirements.txt
export GEMINI_API_KEY=sk-...

# CLI mode
python main.py --email sample_email.txt

# Output:
# ═══════════════════════════════════════════════════════════════
#   EMAIL CLASSIFICATION RESULT
# ═══════════════════════════════════════════════════════════════
#   📧 Simplified:
#      Can you approve the Q2 budget proposal by end of week?
# 
#   🏷️  Category  : Action Item  (confidence: 95%)
#   🔴 Priority  : HIGH  [██████████] 10/10
#   💡 Reason    : Urgent deadline + financial decision required
# ═══════════════════════════════════════════════════════════════
```

## Deployment Subsystem (`aether/subsystems/app_deployer/`)

✅ **Complete & Production-Ready**

Orchestrates end-to-end deployment of Aether applications across a VM pool.

### Deployment Flow

```
1. config.yaml (distribution topology)
        ↓
2. Distributor (map nodes → VMs)
        ↓
3. RuntimeGenerator (config → _aether_main.py)
        ↓
4. AppDeployer (SSH/SCP/pip)
        ↓
5. ProcessManager (systemd units + start)
        ↓
6. DeploymentRecord (status tracking)
        ↓
✓ Running artifacts on VM pool
```

### Quick Start

```python
from aether.subsystems.app_deployer import AppDeployerService
from pathlib import Path

service = AppDeployerService()

# Deploy email classifier to VM pool
deployment = service.deploy(
    app_id="email-classifier-agent",
    app_version="1.0.0",
    zip_path=Path("dist/email-classifier-agent-1.0.0.zip"),
    config_path=Path("apps/email_classifier/config.yaml"),
    vm_pool_path=Path("infra/vm_pool.json"),
    ssh_key=Path("~/.ssh/platform-key.pem"),
    ssh_user="ubuntu",
)

# Check results
print(f"Status: {deployment.status}")  # ✓ SUCCEEDED
for proc in deployment.process_records:
    print(f"  {proc.artifact_id} → {proc.vm_ip}:{proc.port}")
```

### What Gets Generated

**_aether_main.py** (auto-generated from template)
- FastAPI server per artifact role
- Dynamically imports user's artifact classes
- Supports `--role agent | tool | orchestrator | model`
- Serves `/run` (POST) and `/health` (GET) endpoints

**Systemd Service Units** (auto-generated)
- Service name: `aether-<app_id>-<artifact_id>`
- Auto-restart on failure
- Resource limits: 2GB memory, 75% CPU
- Journald logging

### Core Components

| Component | Purpose | Input | Output |
|-----------|---------|-------|--------|
| **RuntimeGenerator** | Transform config → FastAPI wrapper | config.yaml | _aether_main.py |
| **Distributor** | Map nodes to VMs | config.yaml + vm_pool.json | Augmented config |
| **AppDeployer** | SSH/SCP/pip orchestration | app.zip + config | Deployed app on VM |
| **ProcessManager** | Systemd lifecycle | ServiceConfig | Running processes |
| **AppDeployerService** | Main orchestrator | All of above | DeploymentRecord |

### Configuration Example

```yaml
# apps/email_classifier/config.yaml

app:
  name: email-classifier-agent
  version: "1.0.0"
  author: "Platform"
  runtime: python3.11

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
      provider: google
      model_id: gemini-2.5-flash

distribution:
  mode: distributed
  topology: microservices
  
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
    
    - node_id: orchestrator-node-1
      role: orchestrator
      port: 8003
      artifacts:
        - email-pipeline-orchestrator
    
    - node_id: model-node-1
      role: model
      port: 8201
      artifacts:
        - email-llm-model
```

### VM Pool Configuration

```json
// infra/vm_pool.json
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
    },
    {
      "name": "vm-2",
      "ip": "192.168.1.11",
      "roles": ["tool", "model"],
      "status": "healthy",
      "cpu_pct": 40.0,
      "ram_pct": 75.0,
      "latency_ms": 3.2
    }
  ]
}
```

### Data Models

**DeploymentRecord**
```python
@dataclass
class DeploymentRecord:
    deployment_id: str
    app_id: str
    app_version: str
    status: DeploymentStatus  # pending | in_progress | succeeded | failed
    process_records: list[ProcessRecord]
    error_message: str
```

**ProcessRecord**
```python
@dataclass
class ProcessRecord:
    process_id: str
    app_id: str
    artifact_id: str
    artifact_type: str  # agent | tool | orchestrator | model
    vm_ip: str
    port: int
    systemd_service: str
    status: ProcessStatus  # starting | running | stopped | crashed
    pid: Optional[int]
    error_message: str
```

### CLI Tools

Each component is independently testable:

```bash
# Generate runtime from config
python -m aether.subsystems.app_deployer.runtime_generator \
    config.yaml --output _aether_main.py

# Distribute nodes to VMs
python -m aether.subsystems.app_deployer.distributor \
    config.yaml --vm-pool vm_pool.json

# Deploy to a single VM
python -m aether.subsystems.app_deployer.deployer \
    192.168.1.10 --username ubuntu --key ~/.ssh/id_rsa \
    --app-id email-classifier-agent --app-version 1.0.0 \
    --zip app.zip --config config.yaml

# Manage systemd services
python -m aether.subsystems.app_deployer.process_manager \
    192.168.1.10 --action start \
    --app-id email-classifier-agent --artifact-id text-simplifier

# Full deployment end-to-end
python -m aether.subsystems.app_deployer.service \
    --app-id email-classifier-agent \
    --app-version 1.0.0 \
    --zip dist/app.zip \
    --config config.yaml \
    --vm-pool infra/vm_pool.json \
    --key ~/.ssh/id_rsa \
    --output deployment.json
```

### How Deployment Works (Mode B: Distributed)

1. **Distributor** reads `distribution.nodes` from config.yaml
   - Queries vm_pool.json for available VMs
   - Assigns healthiest VM to each node
   
2. **For each VM**:
   - SSH connect (Paramiko)
   - SCP upload app.zip to `/opt/aether/apps/<app_id>/<version>/`
   - Unzip + create virtualenv + pip install dependencies
   - Generate _aether_main.py (Jinja2 template → FastAPI wrapper)
   
3. **For each artifact**:
   - Generate systemd `.service` file
   - Deploy to `/etc/systemd/system/`
   - `systemctl daemon-reload && systemctl start <service>`
   - Poll `/health` endpoint (timeout 30s)
   
4. **Return results**:
   - DeploymentRecord with all process records
   - Status: SUCCEEDED or FAILED
   - Error messages if failed

### Generated Systemd Service Example

```ini
# /etc/systemd/system/aether-email-classifier-agent.service

[Unit]
Description=Aether agent service: email-classifier-agent
After=network.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/aether/apps/email-classifier-agent/1.0.0
ExecStart=/opt/aether/apps/email-classifier-agent/1.0.0/.venv/bin/python \
    _aether_main.py --role agent --artifact email-classifier-agent --port 8001

Restart=on-failure
RestartSec=5
StartLimitInterval=300
StartLimitBurst=5

StandardOutput=journal
StandardError=journal
SyslogIdentifier=aether-email-classifier-agent

MemoryLimit=2G
CPUQuota=75%

[Install]
WantedBy=multi-user.target
```

## Deployment Architecture Options

The platform supports three deployment modes (choose one via `distribution.mode`):

### Mode A: Local (Development)

```yaml
distribution:
  mode: local      # All artifacts in one process
```

- Single Python process on local machine
- All artifacts imported in-memory
- Agent + Tools + Orchestrator + Model in one FastAPI server
- Best for: Development, testing, single-machine deployments

**Runtime:**
```bash
python _aether_main.py --role agent --port 8000
```

### Mode B: Distributed (Production - Current)

```yaml
distribution:
  mode: distributed
  
  nodes:
    - node_id: agent-node-1
      artifacts: [email-classifier-agent]
      port: 8001
    - node_id: tool-node-1
      artifacts: [text-simplifier, email-categorizer, priority-scorer]
      port: 8002
```

- One process per artifact (or per role)
- Each runs on assigned VM
- Communicate via HTTP/JSON
- Best for: Production, scaling, isolation

**Generated services:**
```
aether-email-classifier-agent (port 8001)
aether-text-simplifier (port 8102)
aether-email-categorizer (port 8102)
aether-priority-scorer (port 8102)
```

### Mode C: Containerized (Future)

```yaml
distribution:
  mode: containerized
  
  nodes:
    - node_id: agent-container
      artifacts: [email-classifier-agent]
```

- Generate Docker Compose files
- One container per artifact
- Portable, reproducible, auto-scaling

## Platform Subsystems (In Progress)

The following subsystems are designed but not yet implemented:

### User Management
- Register / login with username + password
- Issue JWT tokens for dashboard sessions
- API key management for programmatic access
- Role-based access control (developer, admin, viewer)

### App Validator
- Validate app structure (required files/folders)
- Parse and validate config.yaml
- Check artifact class inheritance
- Verify dependencies in requirements.txt
- Return validation report

### App Registry
- Store validated app ZIPs
- Maintain version history
- Track deployment records
- Searchable by app_id, name, author

### VM Health Checker
- Periodic SSH ping + HTTP /health probes
- Monitor CPU/RAM/latency per VM
- Maintain health snapshot
- Publish to Kafka topic

### App Health Checker
- Poll /health endpoint per deployed app
- Track failure counts
- Auto-trigger restarts via Lifecycle Manager
- Dashboard status reporting

### Lifecycle Manager
- Start / stop / restart apps
- Scale applications (add more VM nodes)
- Rollback to previous version
- REST API: `/apps/:id/start`, `/apps/:id/stop`, etc.

### CLI Generator
- Read app config
- Generate usage documentation
- Include example commands, options, arguments

### Build Packager
- Build apps from git repo or ZIP
- Syntax check all Python files
- Create validated .aether.zip with manifest
- Dry-run pip install to verify dependencies
- Expose `POST /apps/build` for platform automation

### Notification Service
- Subscribe to platform Kafka topics
- Send notifications on events
- Channels: email, webhook, dashboard push
- Example: "Your app is deployed at 192.168.1.10:8001"

## Architecture Diagrams

### Platform Overview

```
┌─────────────────────────────────────────────┐
│    Developer Dashboard (Web UI)             │
│  Register • Login • Upload ZIP • View Apps  │
└────────────────┬────────────────────────────┘
                 │
┌────────────────▼────────────────────────────┐
│    API Gateway + Load Balancer              │
│  Auth • Rate limiting • Route to subsystems │
└────────────────┬────────────────────────────┘
                 │
      ┌──────────┼──────────┬─────────────┐
      │          │          │             │
      ▼          ▼          ▼             ▼
  User Mgmt  App Validator  App Registry  VM Health
                                         Checker
      │          │          │             │
      └──────────┼──────────┼─────────────┘
                 │
            ┌────▼────┐
            │  Kafka  │
            │  Message│
            │   Bus   │
            └────┬────┘
                 │
      ┌──────────┼──────────┬──────────────┐
      │          │          │              │
      ▼          ▼          ▼              ▼
   App Deployer App Health  Lifecycle  CLI Gen +
              Checker      Manager    Build Pack
      │
      └─────► SSH/SCP to VM Pool
              │
              ▼
         Running Apps on VMs
         (systemd services)
```

### Deployment Flow

```
config.yaml
    │
    ├─ artifacts.agents
    │  artifacts.tools
    │  artifacts.orchestrators
    │  artifacts.models
    │
    ├─ distribution.nodes
    │  [node_id, role, port, artifacts[]]
    │
    ▼
[Distributor] ──► vm_pool.json
    │              (find healthy VMs)
    │
    ▼
Distribution augmented with vm_ip per node
    │
    ├─ Group by VM
    │  {192.168.1.10: [node1, node2],
    │   192.168.1.11: [node3]}
    │
    ▼
[For each VM]
    │
    ├─ SSH connect
    ├─ SCP upload app.zip
    ├─ Unzip + pip install
    ├─ [RuntimeGenerator] create _aether_main.py
    ├─ [ProcessManager] create systemd units
    │
    ▼
systemctl start aether-<app>-<artifact>
    │
    ▼
Poll /health endpoint (max 30s)
    │
    ▼
DeploymentRecord with ProcessRecords
```

## API Examples

### Deploy Application

```python
from aether.subsystems.app_deployer import AppDeployerService
from pathlib import Path
import json

service = AppDeployerService()

deployment = service.deploy(
    app_id="email-classifier-agent",
    app_version="1.0.0",
    zip_path=Path("dist/email-classifier-agent-1.0.0.zip"),
    config_path=Path("apps/email_classifier/config.yaml"),
    vm_pool_path=Path("infra/vm_pool.json"),
    ssh_key=Path("~/.ssh/platform-key.pem"),
    ssh_user="ubuntu",
)

# Print status
print(json.dumps(service.status(deployment), indent=2))
```

### Get Deployment Status

```python
status = service.status(deployment)
# {
#   "deployment_id": "uuid-...",
#   "app_id": "email-classifier-agent",
#   "status": "succeeded",
#   "process_count": 4,
#   "processes": [
#     {
#       "artifact_id": "email-classifier-agent",
#       "vm_ip": "192.168.1.10",
#       "port": 8001,
#       "status": "running",
#       "systemd_service": "aether-email-classifier-agent"
#     },
#     ...
#   ]
# }
```

## Requirements

### Platform Core
```
Python 3.11+
```

### App Deployer
```
paramiko==3.4.0          # SSH/SFTP
Jinja2==3.1.2            # Templates
PyYAML==6.0              # YAML parsing
requests==2.31.0         # HTTP
fastapi==0.104.0         # FastAPI (for _aether_main.py)
uvicorn==0.24.0          # ASGI server (for _aether_main.py)
```

### Sample App (email_classifier)
```
google-generativeai>=0.3.0  # Gemini API
fastapi==0.104.0
uvicorn==0.24.0
requests==2.31.0
pydantic==2.5.0
```

## Running the Sample App

```bash
# Install dependencies
cd apps/email_classifier
pip install -r requirements.txt

# Set Gemini API key
export GEMINI_API_KEY=sk-...

# Run CLI mode
python main.py --email sample_email.txt

# Or interactive mode
echo "Call me ASAP about the urgent contract" | python main.py --stdin

# Or server mode (not yet implemented in sample)
python _aether_main.py --role agent --port 8000
# GET  http://localhost:8000/health
# POST http://localhost:8000/run with {"email": "..."}
```

## Testing Deployment Locally

```bash
# 1. Generate runtime
python -m aether.subsystems.app_deployer.runtime_generator \
    apps/email_classifier/config.yaml \
    --output /tmp/test_main.py

# 2. Verify it loads
python /tmp/test_main.py --help

# 3. See structure
cat /tmp/test_main.py | head -50
```

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — Full platform architecture & subsystem specs
- **[DEPLOYER.md](DEPLOYER.md)** — Deployment modes, runtime design, SSH orchestration
- **[aether/subsystems/app_deployer/README.md](aether/subsystems/app_deployer/README.md)** — Detailed deployer guide
- **[aether/subsystems/cli_generator/README.md](aether/subsystems/cli_generator/README.md)** — CLI usage doc generator guide
- **[aether/subsystems/build_packager/README.md](aether/subsystems/build_packager/README.md)** — Build/package workflow guide

## Key Concepts

### Artifacts

Each artifact is a Python class that inherits from a platform base class:

- **Agent** — Top-level orchestrator; exposes `run(**inputs)` to external world
- **Tool** — Stateless microservice; single responsibility (parsing, API call, etc.)
- **Orchestrator** — Coordinates sequence/DAG of tools; owns data flow
- **Model** — LLM/embedding provider wrapper; uniform interface

All artifacts are **deployable independently** — can run on different VMs and communicate via HTTP.

### Distribution Topology

The `distribution.nodes` section in config.yaml defines:

```yaml
nodes:
  - node_id: agent-node-1      # Unique ID for this node
    role: agent                 # Type of artifact(s) this node runs
    port: 8001                  # HTTP port on VM
    artifacts:                  # List of artifact IDs
      - email-classifier-agent  # (must be declared in artifacts section)
```

The deployer reads this and:
1. Selects a VM for each node from the pool
2. Launches a FastAPI server per artifact
3. Each server exposes `/run` and `/health` endpoints

### Health Checks

All deployed artifacts must implement `/health` endpoint:

```bash
GET /health
→ {"status": "ok", "artifact_id": "..."}
```

The deployer waits up to 30 seconds for each process to respond, then marks deployment as complete.

## Future Roadmap

- [ ] User Management subsystem (auth, RBAC, API keys)
- [ ] App Validator subsystem (structure & config validation)
- [ ] App Registry subsystem (store, version, search apps)
- [ ] VM Health Checker subsystem (real-time VM monitoring)
- [x] App Health Checker subsystem (monitor deployed app endpoints)
- [ ] Lifecycle Manager subsystem (start, stop, scale, restart)
- [x] CLI Generator subsystem (generate usage documentation)
- [x] Build Packager subsystem (build from source, verify deps)
- [x] Notification Service subsystem (email, webhook, dashboard)
- [ ] Web Dashboard (React/Vue UI for deployment & monitoring)
- [ ] Mode C: Containerized deployment (Docker Compose generation)
- [ ] Blue-green & canary deployment strategies
- [ ] Secrets management (vault integration)
- [ ] Observability (Prometheus metrics, tracing)

## Bootstrap

Use the platform bootstrap script to bring up Kafka, master node, VM placeholders, Nginx, backend services, and dashboard:

```bash
bash scripts/bootstrap_platform.sh
```

## License

[LICENSE]

## Contact

For questions or contributions, contact the AetherAgents team.




Distributed agentic AI platform for deploying, managing, and monitoring AI agent applications across VM pools.

---

## What's Built

| Component | Status | Notes |
|---|---|---|
| `core/` — base classes | ✅ Done | `BaseModel`, `BaseTool`, `BaseOrchestrator`, `BaseAgent` |
| `apps/email_classifier/` — sample app | ✅ Done | Full working example app |
| `dashboard/` — React UI | ✅ Done | Login, Register, Dashboard, Deploy, AppDetail pages |
| `subsystems/user_management/` — FastAPI backend | ✅ Done | Register, login, JWT sessions, API keys, RBAC |
| `gateway/`, all other subsystems | 🔲 Pending | To be built by respective teams |

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (running locally)

---

## Setup

### 1. Database (one-time)

```bash
psql postgres -c "CREATE USER aether WITH PASSWORD 'aether_pass';"
psql postgres -c "CREATE DATABASE aetherdb OWNER aether;"
```

### 2. Environment config (one-time)

```bash
cd aether
cp .env.example .env
# Edit .env — set DATABASE_URL to your local PostgreSQL username:
# DATABASE_URL=postgresql://<your_mac_username>@localhost:5432/aetherdb
```

---

## Running the Platform

### Backend — User Management

```bash
cd aether
python -m venv .venv
source .venv/bin/activate
pip install -r subsystems/user_management/requirements.txt
python -m uvicorn subsystems.user_management.service:app --reload --port 8000
```

- API: `http://localhost:8000`
- Interactive docs (Swagger): `http://localhost:8000/docs`

### Frontend — Dashboard

```bash
cd aether/dashboard
npm install
npm run dev
```

- UI: `http://localhost:5173`

---

## User Management API

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/register` | None | Create account |
| `POST` | `/login` | None | Get JWT token |
| `GET` | `/me` | JWT or API key | Get current user profile |
| `POST` | `/api-keys` | JWT | Create API key |
| `GET` | `/api-keys` | JWT | List API keys |
| `DELETE` | `/api-keys/{id}` | JWT | Revoke API key |
| `GET` | `/health` | None | Health check |

**Auth options:**
- `Authorization: Bearer <jwt>` — for dashboard/browser sessions
- `X-API-Key: sk-ae-...` — for programmatic/CLI access

---

## Project Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for full system design, Kafka topics, VM pool schema, and subsystem responsibilities.
