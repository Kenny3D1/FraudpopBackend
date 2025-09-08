# FraudPop – FastAPI Backend + Defender3D Risk Vault (Skeleton)

Implements:

- FastAPI backend
- Defender3D **Risk Vault** (hashed/salted email/device/ip with outcomes)
- `/vault/query` + `/vault/observe`
- `/v1/capture` (device/session capture)
- Shopify `orders/create` webhook (HMAC + idempotency)
- Theme App Extension `fraudpop.js`

## Quickstart

1. `cp .env.example .env` and fill values
2. Start Postgres & Redis; update `.env`
3. `python -m venv .venv && source .venv/bin/activate`
4. `pip install -r requirements.txt`
5. `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

## Structure

backend/app: FastAPI code
theme-app-extension: JS + Liquid snippet

## Notes

- Hashing uses SHA-256 with a **pepper** + per-record random salt — no raw PII in Risk Vault.
- Replace FPJS stub in `fraudpop.js` with your implementation.
