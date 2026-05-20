# AetherAgents Platform — Full Architecture Specification

---

## Project Structure

```
AetherAgents/
│
├── aether/                          # Platform codebase (you own this)
│   ├── core/                          # Base artifact classes (already built)
│   │   ├── __init__.py
│   │   ├── base_model.py
│   │   ├── base_tool.py
│   │   ├── base_orchestrator.py
│   │   └── base_agent.py
│   │
│   ├── subsystems/                    # Each subsystem is a standalone service
│   │   ├── __init__.py
│   │   │
│   │   ├── user_management/
│   │   │   ├── __init__.py
│   │   │   ├── service.py             # FastAPI app
│   │   │   ├── models.py              # DB models (User, APIKey, Session)
│   │   │   ├── auth.py                # JWT / API key auth
│   │   │   ├── rbac.py                # Role-based access control
│   │   │   └── routes.py              # /register /login /me /api-keys
│   │   │
│   │   ├── app_validator/
│   │   │   ├── __init__.py
│   │   │   ├── service.py
│   │   │   ├── structure_validator.py  # Checks file/folder layout
│   │   │   ├── config_validator.py     # Parses and validates config.yaml
│   │   │   ├── artifact_validator.py   # Checks class presence + inheritance
│   │   │   ├── metadata_validator.py   # Version, author, name, semver
│   │   │   ├── dependency_validator.py # requirements.txt parseable?
│   │   │   └── report.py              # ValidationReport dataclass
│   │   │
│   │   ├── app_registry/
│   │   │   ├── __init__.py
│   │   │   ├── service.py
│   │   │   ├── models.py              # AppRecord, AppVersion, DeploymentRecord
│   │   │   ├── store.py               # Saves ZIP + unpacked app to apps/ dir
│   │   │   └── routes.py              # /register /list /get/:id /versions
│   │   │
│   │   ├── vm_health_checker/
│   │   │   ├── __init__.py
│   │   │   ├── service.py
│   │   │   ├── prober.py              # SSH ping, /health HTTP, CPU/RAM via psutil
│   │   │   ├── scheduler.py           # Runs probes every N seconds
│   │   │   ├── models.py              # VMRecord, HealthSnapshot
│   │   │   └── vm_registry.py         # Loads vm_pool.json, maintains state
│   │   │
│   │   ├── app_deployer/
│   │   │   ├── __init__.py
│   │   │   ├── service.py
│   │   │   ├── deployer.py            # SSH → scp → unzip → pip install → launch
│   │   │   ├── distributor.py         # Reads config.yaml distribution block
│   │   │   ├── process_manager.py     # Starts app processes on remote VMs
│   │   │   └── rollback.py            # Previous version restore
│   │   │
│   │   ├── app_health_checker/
│   │   │   ├── __init__.py
│   │   │   ├── service.py
│   │   │   ├── prober.py              # Polls each app's /health endpoint
│   │   │   ├── scheduler.py           # Periodic health check loop
│   │   │   └── models.py              # AppHealthRecord, ProbeResult
│   │   │
│   │   ├── lifecycle_manager/
│   │   │   ├── __init__.py
│   │   │   ├── service.py
│   │   │   ├── controller.py          # start / stop / restart / scale commands
│   │   │   └── routes.py              # /apps/:id/start  stop  restart  scale
│   │   │
│   │   ├── cli_generator/
│   │   │   ├── __init__.py
│   │   │   ├── service.py
│   │   │   ├── generator.py           # Reads config.yaml → renders CLI doc
│   │   │   └── templates/
│   │   │       └── cli_usage.md.j2    # Jinja2 template
│   │   │
│   │   ├── build_packager/            # NEW — builds + packages apps
│   │   │   ├── __init__.py
│   │   │   ├── builder.py             # pip install, compile checks
│   │   │   └── service.py             # POST /apps/build + CLI wrapper
│   │   │
│   │   └── notification_service/      # NEW — sends events to developer
│   │       ├── __init__.py
│   │       ├── service.py
│   │       └── channels.py            # Email / webhook / dashboard push
│   │
│   ├── gateway/
│   │   ├── __init__.py
│   │   ├── app.py                     # FastAPI main gateway
│   │   ├── load_balancer.py           # Round-robin / least-conn routing
│   │   ├── middleware.py              # Auth, rate limiting, CORS
│   │   └── router.py                  # Routes requests to subsystems
│   │
│   ├── kafka/
│   │   ├── __init__.py
│   │   ├── producer.py                # KafkaProducer wrapper
│   │   ├── consumer.py                # KafkaConsumer wrapper
│   │   └── topics.py                  # Topic name constants
│   │
│   ├── dashboard/                     # Web UI (React / Vue)
│   │   ├── src/
│   │   │   ├── pages/
│   │   │   │   ├── Login.tsx
│   │   │   │   ├── Register.tsx
│   │   │   │   ├── Dashboard.tsx      # App list, status, deploy button
│   │   │   │   ├── Deploy.tsx         # Upload ZIP form
│   │   │   │   └── AppDetail.tsx      # Health, logs, CLI guide
│   │   │   └── components/
│   │   ├── package.json
│   │   └── vite.config.ts
│   │
│   ├── infra/
│   │   ├── vm_pool.json               # VM inventory (see schema below)
│   │   ├── kafka/
│   │   │   └── docker-compose.yml     # Kafka + Zookeeper
│   │   ├── nginx/
│   │   │   └── nginx.conf             # Reverse proxy config
│   │   └── systemd/
│   │       └── aether-*.service       # Systemd unit files per subsystem
│   │
│   ├── config/
│   │   ├── platform.yaml              # Platform-wide settings
│   │   └── logging.yaml
│   │
│   ├── requirements.txt               # Platform Python deps
│   └── bootstrap.sh                   # Linux bootstrap script
│
└── apps/                              # All deployed app artifacts live here
    └── <app_id>/
        └── <version>/
            ├── source/                # Unpacked app source
            │   ├── models/
            │   ├── tools/
            │   ├── orchestrators/
            │   ├── agents/
            │   ├── main.py
            │   ├── config.yaml
            │   └── requirements.txt
            └── <app_id>-<version>.zip # Original ZIP kept for rollback
```

---

## Subsystem Responsibilities

### 1. User Management
- Register / login with username + password (bcrypt hashed)
- Issue JWT tokens for dashboard sessions
- Issue API keys for programmatic access
- Role-based access: `developer`, `admin`, `viewer`
- Kafka topic: `user.events` (login, register, key-created)

### 2. App Validator
Called immediately after ZIP upload. Validates:

**Structure checks**
- `main.py` present at root
- `config.yaml` present at root
- `requirements.txt` present
- Directories: `models/`, `tools/`, `orchestrators/`, `agents/`
- At least one `.py` file in each directory

**Config checks** (parses config.yaml)
- Top-level keys: `app.name`, `app.version`, `app.runtime`
- `artifacts.models` → at least one entry with `class`, `id`
- `artifacts.tools` → same
- `artifacts.orchestrators` → same
- `artifacts.agents` → same
- `entry_points.cli` resolves to `main.py`
- `distribution.mode` is valid
- `distribution.nodes` has at least one node

**Artifact checks** (imports the classes)
- Each declared `class` in config exists in the source
- Each model class subclasses `BaseModel`
- Each tool class subclasses `BaseTool`
- Each orchestrator subclasses `BaseOrchestrator`
- Each agent subclasses `BaseAgent`

**Metadata checks**
- `app.name` is slug-safe (no spaces)
- `app.version` is semver (`X.Y.Z`)
- `app.author` present

Returns a `ValidationReport` with `passed: bool`, list of errors, list of warnings.
Kafka topic: `app.validated`

### 3. App Registry
- Stores validated app ZIP to `apps/<app_id>/<version>/`
- Unpacks source into `apps/<app_id>/<version>/source/`
- Inserts `AppRecord` into metadata DB (PostgreSQL)
- Tracks all versions per app
- Provides lookup by `app_id`, `name`, `author`, `tag`
- Kafka topic: `app.registered`

### 4. VM Health Checker
- Loads `vm_pool.json` on startup
- Every 30 seconds: SSH ping + `/health` HTTP probe + collect CPU/RAM via SSH
- Maintains in-memory `HealthSnapshot` per VM: `{ status, cpu_pct, ram_pct, latency_ms, last_checked }`
- Publishes availability map to Kafka topic `vm.health`
- App Deployer subscribes to this to know which VMs are free

### 5. App Deployer
How apps are deployed across distributed VMs:

1. **Reads `distribution.nodes`** from the app's `config.yaml`
2. **For each node** in the distribution config, selects the healthiest matching VM from the pool
3. **SSH into VM** using credentials from `vm_pool.json`
4. **SCP the app ZIP** to the VM's `/opt/aether/apps/<app_id>/`
5. **On the VM**: unzip, create virtualenv, `pip install -r requirements.txt`
6. **Launch the process**: `python main.py --node-role <role> --node-port <port>`
7. **Registers the running process** in the deployment record (PID, VM IP, port)
8. Reports back via Kafka topic `app.deployed`

Distribution strategy from config is respected:
- `rolling` → deploy node by node, health check between each
- `blue-green` → deploy full new stack, switch traffic, tear down old
- `canary` → deploy to 1 node first, wait, then rest

### 6. App Health Checker
- After deployment, polls each app node's `/health` endpoint every 30 seconds
- If a node fails 3 consecutive checks → publishes `app.unhealthy` to Kafka
- Lifecycle Manager subscribes and can auto-restart
- Developer sees status in dashboard (green / degraded / down)
- Can be triggered manually via API: `POST /apps/:id/health-check`

### 7. Lifecycle Manager
API endpoints and Kafka commands for:
- `start` → SSH to VM, start the process
- `stop` → SSH to VM, kill the process (SIGTERM then SIGKILL)
- `restart` → stop + start
- `scale` → add another VM node for the given role
- `rollback` → undeploy current version, redeploy previous ZIP

### 8. CLI Generator
After deployment, reads the app's `config.yaml` and generates:
```
=== email-classifier-agent CLI Usage ===
Host:    <vm-ip>
Port:    8001
Run:     python main.py --email <file.txt>
Options:
  --email FILE     Path to email .txt file
  --stdin          Read from stdin
  --json           Output raw JSON
  --health         Run health check
  --api-key KEY    Override ANTHROPIC_API_KEY
```
This is sent to the developer via dashboard + email.

### 9. Build Packager (added)
- `POST /apps/build` — takes a git repo URL or raw ZIP
- Runs `pip install --dry-run` to check deps resolve
- Runs Python syntax check on all `.py` files (`py_compile`)
- Packages into a validated `.aether.zip` with a `manifest.json` injected
- Developer can build locally then upload, OR platform can build from source
- Exposed as a FastAPI service in `aether/subsystems/build_packager/service.py`

### 10. Notification Service (added)
- Subscribes to all major Kafka topics
- On `app.validated` → notify: "Validation passed/failed"
- On `app.deployed` → notify: "Your app is live at <IP>:<port>"
- On `app.unhealthy` → notify: "Node X is down — auto-restarting"
- Channels: dashboard push (WebSocket), email (SMTP), webhook (POST to dev's URL)

---

## Kafka Topics

| Topic                | Producer              | Consumer(s)                        |
|----------------------|-----------------------|------------------------------------|
| `user.events`        | User Management       | Notification Service               |
| `app.upload`         | Gateway               | App Validator                      |
| `app.validated`      | App Validator         | App Registry, Notification         |
| `app.registered`     | App Registry          | App Deployer                       |
| `vm.health`          | VM Health Checker     | App Deployer, Lifecycle Manager    |
| `app.deployed`       | App Deployer          | App Health Checker, CLI Gen, Notif |
| `app.health`         | App Health Checker    | Lifecycle Manager, Notification    |
| `app.lifecycle`      | Lifecycle Manager     | App Deployer, Notification         |
| `app.unhealthy`      | App Health Checker    | Lifecycle Manager, Notification    |
| `platform.metrics`   | All subsystems        | Metrics dashboard                  |

---

## vm_pool.json Schema

```json
{
  "pool_id": "prod-pool-01",
  "description": "Production VM pool for AetherAgents",
  "vms": [
    {
      "vm_id": "vm-001",
      "label": "agent-node-1",
      "host": "192.168.1.10",
      "port": 22,
      "username": "ubuntu",
      "auth": {
        "method": "password",
        "password": "secret123"
      },
      "roles": ["agent", "orchestrator"],
      "specs": {
        "cpu_cores": 4,
        "ram_gb": 8,
        "os": "ubuntu-24.04"
      },
      "status": "available",
      "tags": ["gpu", "high-memory"],
      "aether_home": "/opt/aether",
      "python_bin": "/usr/bin/python3.11"
    },
    {
      "vm_id": "vm-002",
      "label": "tool-node-1",
      "host": "192.168.1.11",
      "port": 22,
      "username": "ubuntu",
      "auth": {
        "method": "ssh_key",
        "private_key_path": "/home/ubuntu/.ssh/id_rsa",
        "passphrase": null
      },
      "roles": ["tool"],
      "specs": {
        "cpu_cores": 2,
        "ram_gb": 4,
        "os": "ubuntu-24.04"
      },
      "status": "available",
      "tags": [],
      "aether_home": "/opt/aether",
      "python_bin": "/usr/bin/python3.11"
    }
  ]
}
```

`auth.method` can be `"password"` or `"ssh_key"`.
For production, passwords should be replaced with `ssh_key` and the JSON should be encrypted at rest (use `python-dotenv` + secrets manager).

---

## bootstrap.sh (Linux — Ubuntu 24.04)

```bash
#!/usr/bin/env bash
# AetherAgents Platform Bootstrap
# Run as: sudo bash bootstrap.sh

set -euo pipefail
AETHER_HOME="/opt/aether"
AETHER_USER="aether"

echo "==> [1/8] System update"
apt-get update -y && apt-get upgrade -y
apt-get install -y python3.11 python3.11-venv python3.11-dev \
    pip git curl wget unzip nginx \
    openjdk-17-jdk postgresql postgresql-contrib \
    openssh-client sshpass net-tools

echo "==> [2/8] Create aether user"
id -u $AETHER_USER &>/dev/null || useradd -m -s /bin/bash $AETHER_USER
mkdir -p $AETHER_HOME/{apps,logs,config,infra}
chown -R $AETHER_USER:$AETHER_USER $AETHER_HOME

echo "==> [3/8] Python virtualenv"
python3.11 -m venv $AETHER_HOME/venv
source $AETHER_HOME/venv/bin/activate
pip install --upgrade pip
pip install -r $AETHER_HOME/requirements.txt

echo "==> [4/8] Kafka (via Docker Compose)"
apt-get install -y docker.io docker-compose
systemctl enable docker && systemctl start docker
cp $AETHER_HOME/infra/kafka/docker-compose.yml /opt/kafka-compose.yml
docker-compose -f /opt/kafka-compose.yml up -d

echo "==> [5/8] PostgreSQL setup"
systemctl enable postgresql && systemctl start postgresql
sudo -u postgres psql -c "CREATE USER aether WITH PASSWORD 'aether_pass';" || true
sudo -u postgres psql -c "CREATE DATABASE aetherdb OWNER aether;" || true

echo "==> [6/8] Nginx"
cp $AETHER_HOME/infra/nginx/nginx.conf /etc/nginx/sites-available/aether
ln -sf /etc/nginx/sites-available/aether /etc/nginx/sites-enabled/aether
nginx -t && systemctl reload nginx

echo "==> [7/8] Systemd services"
for svc in gateway user_management app_validator app_registry \
           vm_health_checker app_deployer app_health_checker \
           lifecycle_manager cli_generator notification_service; do
  cp $AETHER_HOME/infra/systemd/aether-${svc}.service /etc/systemd/system/
done
systemctl daemon-reload
systemctl enable aether-gateway aether-user_management \
  aether-app_validator aether-app_registry \
  aether-vm_health_checker aether-app_deployer \
  aether-app_health_checker aether-lifecycle_manager \
  aether-cli_generator aether-notification_service
systemctl start aether-gateway

echo "==> [8/8] Done"
echo "    Platform gateway: http://localhost:8000"
echo "    Dashboard:        http://localhost:3000"
echo "    Kafka:            localhost:9092"
echo "    PostgreSQL:       localhost:5432/aetherdb"
```

---

## Platform Config (platform.yaml)

```yaml
platform:
  name: AetherAgents
  version: "1.0.0"
  env: production       # development | staging | production

gateway:
  host: 0.0.0.0
  port: 8000

kafka:
  bootstrap_servers:
    - "localhost:9092"
  consumer_group: aether-platform

database:
  url: "postgresql://aether:aether_pass@localhost:5432/aetherdb"

vm_pool:
  config_file: infra/vm_pool.json
  health_check_interval: 30   # seconds

apps:
  storage_root: /opt/aether/apps
  max_zip_size_mb: 100

auth:
  jwt_secret: "CHANGE_THIS_IN_PRODUCTION"
  jwt_expire_hours: 24
  api_key_prefix: "sk-ae-"

load_balancer:
  strategy: round_robin    # round_robin | least_connections | random
  health_check_path: /health
```

---

## Subsystem Port Map

| Subsystem              | Port  |
|------------------------|-------|
| API Gateway            | 8000  |
| User Management        | 8010  |
| App Validator          | 8011  |
| App Registry           | 8012  |
| VM Health Checker      | 8013  |
| App Deployer           | 8014  |
| App Health Checker     | 8015  |
| Lifecycle Manager      | 8016  |
| CLI Generator          | 8017  |
| Build Packager         | 8018  |
| Notification Service   | 8019  |
| Dashboard (React)      | 3000  |
| Kafka                  | 9092  |
| PostgreSQL             | 5432  |

All subsystems are internal; only port 8000 (gateway) and 3000 (dashboard) are exposed externally.

