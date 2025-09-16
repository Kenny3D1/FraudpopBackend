# FraudPop – FastAPI Backend & Defender3D Risk Vault

## Features

- **FastAPI backend**: Modular, production-ready API endpoints for fraud/risk intelligence.
- **Risk Vault**: Privacy-preserving storage of hashed/salted identifiers (email, device, IP) with repeat counts and outcomes, updated via Celery background tasks.
- **Order Scoring**: Hybrid rules + adapter scoring via `/webhooks/orders/create` (Shopify webhook).
- **Device/Session Capture**: `/v1/capture` endpoint for device/session data.
- **Background Tasks**: Celery + Redis for async order processing, scoring, and risk signal updates.
- **Security**: HMAC verification for webhooks, Argon2 hashing, Pydantic validation, secrets from env.
- **Evidence Logging**: All risk decisions and input data logged for audit.

## Quickstart

1. `cp .env.example .env` and fill in your secrets and DB/Redis URLs
2. Start Postgres & Redis (see `docker-compose.yml`)
3. `python -m venv .venv && source .venv/bin/activate`
4. `pip install -r requirements.txt`
5. `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
6. Start Celery worker: `celery -A app.tasks worker --loglevel=info`

## Directory Structure

- `app/` – FastAPI backend code
  - `routes/` – API endpoints (webhooks, capture)
  - `models.py` – SQLAlchemy models
  - `schemas.py` – Pydantic schemas
  - `rules/` – Scoring logic (rules, defender3d)
  - `adapters/` – External API adapters (email, IP, device)
  - `vault/` – Hashing and repository logic for identifiers
  - `tasks.py` – Celery background tasks
  - `utils/` – Logging, idempotency, etc.
- `docker-compose.yml` – Local Postgres & Redis setup

## Risk Vault Logic

- Identifiers (email, device, IP) are hashed with Argon2 (see `vault/hasher.py`).
- Repeat counts are tracked in the vault (`vault/repository.py`) and used for scoring.
- No raw PII is stored; only salted hashes and counts.
- Vault is updated automatically by Celery tasks during order processing.

## Scoring & Decisions

- Orders are scored using rules and adapter signals (see `rules/defender3d.py`).
- Vault repeat counts enrich risk decisions.
- Results are written back to Shopify as metafields (see `tasks.py`).

## Security & Best Practices

- All secrets/config from environment variables.
- Webhook HMAC verification is mandatory.
- Argon2 for hashing, Pydantic for validation.
- Evidence logging for all risk decisions.

## Testing & Monitoring

- Unit tests for rules, webhook verification, and idempotency.
- Basic request logging and error monitoring included.

## Notes

- No raw PII is ever stored in the vault.
- You can swap out adapters or scoring logic without re-architecting.
