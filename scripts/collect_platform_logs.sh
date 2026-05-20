#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/.run/diagnostics}"
TS="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="${1:-$OUT_DIR/platform_diag_${TS}.log}"

mkdir -p "$OUT_DIR"

# Send all output to both stdout and the log file.
exec > >(tee -a "$OUT_FILE") 2>&1

log_section() {
  echo
  echo "===== $1 ====="
}

log_section "Header"
echo "Aether platform diagnostics"
echo "Timestamp: $(date -Is)"
echo "Root: $ROOT_DIR"
echo "User: $(id -un)"
echo "Host: $(hostname)"
echo "Kernel: $(uname -sr)"
echo "PWD: $PWD"

echo

log_section "Git status"
if command -v git >/dev/null 2>&1; then
  git -C "$ROOT_DIR" status -sb || true
else
  echo "git not available"
fi

# log_section "Docker compose status"
# if command -v docker >/dev/null 2>&1; then
#   docker compose -f "$ROOT_DIR/infra/docker-compose.platform.yml" ps || true
# else
#   echo "docker not available"
# fi

# log_section "Docker compose logs"
# if command -v docker >/dev/null 2>&1; then
#   docker compose -f "$ROOT_DIR/infra/docker-compose.platform.yml" logs --no-color || true
# else
#   echo "docker not available"
# fi

log_section "PIDs"
if [[ -d "$ROOT_DIR/.run/pids" ]]; then
  for pid_file in "$ROOT_DIR/.run/pids"/*.pid; do
    [[ -e "$pid_file" ]] || { echo "(no pid files)"; break; }
    name="$(basename "$pid_file" .pid)"
    pid="$(cat "$pid_file")"
    if ps -p "$pid" >/dev/null 2>&1; then
      echo "$name: running (pid $pid)"
    else
      echo "$name: not running (pid $pid)"
    fi
  done
else
  echo "no .run/pids directory"
fi

log_section "Service logs (tail 200)"
if [[ -d "$ROOT_DIR/.run/logs" ]]; then
  for log_file in "$ROOT_DIR/.run/logs"/*.log; do
    [[ -e "$log_file" ]] || { echo "(no log files)"; break; }
    echo
    echo "-- $(basename "$log_file")"
    tail -n 200 "$log_file" || true
  done
else
  echo "no .run/logs directory"
fi

log_section "Health endpoints"
urls=(
  "http://localhost:8000/health"
  "http://localhost:8080"
  "http://localhost:3000"
)
for url in "${urls[@]}"; do
  echo "GET $url"
  if command -v curl >/dev/null 2>&1; then
    code="$(curl -s -o /dev/null -w "%{http_code}" "$url" || true)"
    echo "  status: ${code:-error}"
  else
    echo "  curl not available"
  fi
  echo
  done

log_section "Listening ports"
if command -v ss >/dev/null 2>&1; then
  ss -lntp || true
elif command -v netstat >/dev/null 2>&1; then
  netstat -lntp || true
else
  echo "ss/netstat not available"
fi

log_section "Python environment"
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  "$ROOT_DIR/.venv/bin/python" --version || true
  "$ROOT_DIR/.venv/bin/pip" list || true
else
  echo "no local .venv found"
fi

echo
log_section "Done"
echo "Diagnostics saved to: $OUT_FILE"
