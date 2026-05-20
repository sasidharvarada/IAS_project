# App Health Checker

Monitors deployed app artifacts by polling their `/health` endpoints.

## Features

- Register artifact endpoints to monitor
- Periodic background probes (default: every 30s)
- Failure streak tracking per target
- Degraded/down status transitions
- Manual health check trigger for one app or all apps

## API Endpoints

- `POST /health/targets` register a monitored target
- `DELETE /health/targets` unregister a target
- `GET /health/targets` list all monitored targets
- `POST /apps/{app_id}/health-check` run immediate checks for one app
- `POST /health-check` run immediate checks for all apps
- `GET /health/summary` status counts across targets
- `GET /health` service readiness

## CLI Examples

```bash
# Register one target
python -m aether.subsystems.app_health_checker.service \
  --register \
  --app-id email-classifier-agent \
  --app-version 1.0.0 \
  --artifact-id email-classifier-agent \
  --vm-ip 192.168.1.10 \
  --port 8001 \
  --json

# Run one immediate check for all registered targets
python -m aether.subsystems.app_health_checker.service --check-now --json
```
