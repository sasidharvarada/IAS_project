# Aether API Contracts (v1)

## Version
- `v1` is the active integration contract as of 2026-05-06.

## Gateway
- `POST /v1/apps/deploy`
  - Purpose: End-to-end build + validate + deploy + lifecycle registration.
  - Request fields:
    - `source` (required)
    - `config_path`, `output`, `vm_pool_path`, `ssh_key`, `ssh_user`
    - `skip_dependency_check`, `skip_syntax_check`
    - `app_health_checker_url`
  - Response:
    - `stage`, `build`, `validation`, `deployment`
- `GET /v1/apps/{app_id}/status`
- `GET /v1/contracts`
- `POST /v1/apps/deploy/upload` (multipart ZIP upload path for UI)

## App Validator
- `POST /validate` (multipart form with `file`)
- `GET /health`

## App Deployer
- Python service interface:
  - `AppDeployerService.deploy(...)`
  - `AppDeployerService.status(...)`
- Auto-calls Health Checker registration endpoint:
  - `POST {AETHER_APP_HEALTH_CHECKER_URL}/health/targets`
- Publishes Kafka event:
  - `app.deployed`

## App Health Checker
- `POST /health/targets`
- `DELETE /health/targets`
- `GET /health/targets`
- `POST /apps/{app_id}/health-check`
- `POST /health-check`
- `GET /health/summary`
- `GET /health`
- Consumes Kafka event:
  - `app.deployed` (auto-register targets)
- On unhealthy threshold publishes Kafka event:
  - `app.unhealthy`

## Lifecycle Manager
- `POST /apps/{app_id}/register`
- `GET /apps/{app_id}/status`
- `POST /apps/{app_id}/start`
- `POST /apps/{app_id}/stop`
- `POST /apps/{app_id}/restart`
- `POST /apps/{app_id}/scale`
- `POST /apps/{app_id}/rollback`
- `GET /health`
- Consumes Kafka events:
  - `app.deployed` (register deployment state)
  - `app.unhealthy` (trigger restart)
- Publishes Kafka event:
  - `app.lifecycle` (e.g., `app.restarted`)

## Notification Service
- `POST /notify/email`
- `POST /notify/event`
- `GET /health`
- Consumes Kafka events:
  - `app.unhealthy`
  - `app.lifecycle`
  - `app.deployed`

## User Management
- `POST /register`
- `POST /login`
- `GET /me`
- `POST /api-keys`
- `GET /api-keys`
- `DELETE /api-keys/{key_id}`
- `GET /health`

## Required Integration Environment Variables
- `AETHER_APP_HEALTH_CHECKER_URL`
- `AETHER_LIFECYCLE_MANAGER_URL`
- `AETHER_NOTIFICATION_SERVICE_URL`
- `AETHER_ALERT_EMAIL`
- `KAFKA_BOOTSTRAP_SERVERS`
- `AETHER_ALLOW_SIMULATED_DEPLOY` (default `true` for local bootstrap)
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_USE_TLS`
