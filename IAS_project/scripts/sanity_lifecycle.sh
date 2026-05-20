#!/usr/bin/env bash
set -euo pipefail

APP_ID=${1:-email-classifier-agent}
BASE_URL=${2:-http://localhost:8000}

status() {
  curl -sS "$BASE_URL/v1/apps/$APP_ID/status"
  echo
}

action() {
  local action="$1"
  local replicas="${2:-}"
  local payload=""

  if [[ -n "$replicas" ]]; then
    payload="{\"action\":\"$action\",\"replicas\":$replicas}"
  else
    payload="{\"action\":\"$action\"}"
  fi

  echo ">>> $action ${replicas}"
  curl -sS -X POST "$BASE_URL/v1/apps/$APP_ID/lifecycle" \
    -H 'Content-Type: application/json' \
    -d "$payload"
  echo
}

echo "Lifecycle sanity for $APP_ID at $BASE_URL"
status
action start
status
action scale 2
status
action restart
status
action stop
status
