# Notification Service

Sends platform notifications via SMTP. SMTP credentials are loaded from `.env`.

## Required .env keys

- `SMTP_HOST`
- `SMTP_PORT` (default: 587)
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_USE_TLS` (default: true)

## API Endpoints

- `POST /notify/email`
- `POST /notify/event`
- `GET /health`

## CLI Example

```bash
python -m aether.subsystems.notification_service.service \
  --to dev@example.com \
  --subject "Deployment complete" \
  --body "App email-classifier-agent v1.0.0 deployed successfully" \
  --json
```
