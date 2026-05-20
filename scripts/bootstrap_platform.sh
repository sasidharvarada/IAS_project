#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/.run/logs"
PID_DIR="$ROOT_DIR/.run/pids"

mkdir -p "$LOG_DIR" "$PID_DIR"

# Stop any previously started services from earlier runs (clean PIDs and dev servers)
if [ -d "$PID_DIR" ]; then
  echo "[0/6] Stopping previous platform services (if any)..."
  for f in "$PID_DIR"/*.pid; do
    [ -f "$f" ] || continue
    pid=$(cat "$f" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      echo "  - stopping pid $pid (from $f)"
      kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$f" 2>/dev/null || true
  done
fi

# Kill any dev servers that might be occupying typical dashboard ports
for port in 3000 3001 3002 3003; do
  pids=$(lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "  - killing processes listening on :$port -> $pids"
    kill $pids 2>/dev/null || kill -9 $pids 2>/dev/null || true
  fi
done

# Ensure log and pid directories are writable by current user
if [ ! -w "$LOG_DIR" ] || [ ! -w "$PID_DIR" ]; then
  echo "Error: $LOG_DIR or $PID_DIR is not writable by $(whoami)."
  echo "If these are owned by root from a previous run, fix with:" 
  echo "  sudo chown -R $(whoami) \"$ROOT_DIR/.run\""
  echo "Then re-run scripts/bootstrap_platform.sh as your normal user (no sudo)."
  exit 1
fi

echo "[1/6] Starting infra containers (Kafka, master node, VMs, nginx)..."
#if already running, restart to ensure they're up-to-date with the latest config
if docker compose -f "$ROOT_DIR/infra/docker-compose.platform.yml" ps -q | grep -q .; then
  docker compose -f "$ROOT_DIR/infra/docker-compose.platform.yml" restart
else
  docker compose -f "$ROOT_DIR/infra/docker-compose.platform.yml" up -d
fi

echo "[2/6] Preparing Python env (local)..."
# If a previous .venv exists and is not writable, fail fast with instructions
if [ -d "$ROOT_DIR/.venv" ] && [ ! -w "$ROOT_DIR/.venv" ]; then
  echo "Error: .venv exists but is not writable by $(whoami)."
  echo "If this directory is owned by root from a previous run, remove or chown it:" 
  echo "  sudo rm -rf $ROOT_DIR/.venv"
  echo "  sudo chown -R $(whoami) $ROOT_DIR/.venv"
  echo "Then re-run scripts/bootstrap_platform.sh as your normal user (no sudo)."
  exit 1
fi

python3 -m venv "$ROOT_DIR/.venv"
source "$ROOT_DIR/.venv/bin/activate"
pip install --upgrade pip >/dev/null
pip install \
  fastapi==0.110.0 uvicorn==0.24.0 pydantic==2.9.2 anyio==4.8.0 \
  python-dotenv==1.0.0 email-validator==2.2.0 \
  kafka-python==2.0.2 pyyaml==6.0 requests==2.31.0 \
  jinja2==3.1.2 paramiko==3.4.0 sqlalchemy==2.0.31 \
  bcrypt==4.1.3 python-jose==3.3.0 psycopg2-binary==2.9.9 \
  python-multipart==0.0.6 httpx==0.28.1 google-genai==1.75.0 >/dev/null

export KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}"
export AETHER_APP_HEALTH_CHECKER_URL="${AETHER_APP_HEALTH_CHECKER_URL:-http://localhost:8015}"
export AETHER_LIFECYCLE_MANAGER_URL="${AETHER_LIFECYCLE_MANAGER_URL:-http://localhost:8016}"
export AETHER_NOTIFICATION_SERVICE_URL="${AETHER_NOTIFICATION_SERVICE_URL:-http://localhost:8019}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$ROOT_DIR/.run/aether.db}"
export AETHER_USER_MANAGEMENT_URL="${AETHER_USER_MANAGEMENT_URL:-http://localhost:8001}"
export AETHER_APP_VALIDATOR_URL="${AETHER_APP_VALIDATOR_URL:-http://localhost:8011}"
export AETHER_APP_REGISTRY_STORAGE_DIR="${AETHER_APP_REGISTRY_STORAGE_DIR:-$ROOT_DIR/.run/storage}"
export AETHER_APP_REGISTRY_DIR="${AETHER_APP_REGISTRY_DIR:-$ROOT_DIR/.run/storage/apps}"
export PYTHONPATH="$ROOT_DIR"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

run_service() {
  local name="$1"
  local module="$2"
  local port="$3"
  local log_file="$LOG_DIR/$name.log"
  local pid_file="$PID_DIR/$name.pid"
  echo "  - starting $name on :$port"
  nohup "$ROOT_DIR/.venv/bin/python" -m uvicorn "$module:app" --host 0.0.0.0 --port "$port" >"$log_file" 2>&1 &
  echo $! > "$pid_file"
}

stop_port() {
  local port="$1"
  local pids=""

  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  elif command -v ss >/dev/null 2>&1; then
    pids="$(ss -lntp "sport = :$port" 2>/dev/null | awk -F'pid=|,' '/pid=/{print $2}' | sort -u)"
  fi

  for pid in $pids; do
    [[ -n "$pid" ]] || continue
    if kill -0 "$pid" 2>/dev/null; then
      echo "  - freeing port $port (pid $pid)"
      kill "$pid" 2>/dev/null || true
      for _ in {1..10}; do
        if kill -0 "$pid" 2>/dev/null; then
          sleep 0.3
        else
          break
        fi
      done
      if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
      fi
    fi
  done
}

stop_service() {
  local name="$1"
  local pid_file="$PID_DIR/$name.pid"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "  - stopping $name (pid $pid)"
      kill "$pid" 2>/dev/null || true
      for _ in {1..10}; do
        if kill -0 "$pid" 2>/dev/null; then
          sleep 0.3
        else
          break
        fi
      done
    fi
    rm -f "$pid_file"
  fi
}

echo "[3/6] Starting backend subsystems..."
stop_port 8001
stop_port 8011
stop_port 8012
stop_port 8013
stop_port 8015
stop_port 8016
stop_port 8019
stop_port 8000
stop_service "user_management"
stop_service "app_validator"
stop_service "app_registry"
stop_service "vm_health_checker"
stop_service "app_health_checker"
stop_service "lifecycle_manager"
stop_service "notification_service"
stop_service "gateway"
run_service "user_management" "aether.subsystems.user_management.service" 8001
run_service "app_validator" "aether.subsystems.app_validator.service" 8011
run_service "app_registry" "aether.subsystems.app_registry.app_registry" 8012
run_service "vm_health_checker" "aether.subsystems.vm_health_checker.service" 8013
run_service "app_health_checker" "aether.subsystems.app_health_checker.service" 8015
run_service "lifecycle_manager" "aether.subsystems.lifecycle_manager.service" 8016
run_service "notification_service" "aether.subsystems.notification_service.service" 8019
run_service "gateway" "aether.gateway.app" 8000

echo "[4/6] Starting platform UI..."
pushd "$ROOT_DIR/aether/dashboard" >/dev/null
npm install >/dev/null
stop_service "dashboard"
stop_port 3000
nohup npm run dev -- --host 0.0.0.0 --port 3000 --strictPort >"$LOG_DIR/dashboard.log" 2>&1 &
echo $! > "$PID_DIR/dashboard.pid"
popd >/dev/null

echo "[5/6] Waiting for gateway health..."
for i in {1..30}; do
  if curl -sf "http://localhost:8000/health" >/dev/null; then
    break
  fi
  sleep 1
done

echo "[6/6] Platform bootstrapped."
echo "Gateway: http://localhost:8000"
echo "Dashboard UI: http://localhost:3000"
echo "Nginx LB: http://localhost:8080"
echo "Kafka: localhost:9092"
echo "Master node shared repo mount: /shared-repo (inside aether-master-node)"
