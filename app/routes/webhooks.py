from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
import json
import httpx
from datetime import timedelta

from ..database import get_db, Base, engine
from ..utils.shopify import verify_shopify_hmac
from ..utils.idempotency import is_processed, mark_processed
from ..config import settings
from ..schemas import QueryInput
from ..services.scoring import compute_risk
from .vault import query_core
from ..utils.logging import logger

router = APIRouter(prefix="/webhooks", tags=["shopify"])
Base.metadata.create_all(bind=engine)

SHOPIFY_API_VERSION = getattr(settings, "SHOPIFY_API_VERSION", "2025-07")
RISK_NAMESPACE = "fraudpop"
RISK_KEY = "risk"


async def write_order_risk_metafield(
    shop_domain: str,
    order_id: int,
    token: str,
    risk_payload: dict,
) -> dict:
    """
    Writes a JSON metafield:
      namespace: fraudpop
      key: risk
      type: json
      value: {"score": int, "verdict": "green|amber|red", "reasons": [...], "at": "...iso..."}
    """
    base = f"https://{shop_domain}/admin/api/{SHOPIFY_API_VERSION}"
    url = f"{base}/orders/{order_id}/metafields.json"

    body = {
        "metafield": {
            "namespace": RISK_NAMESPACE,
            "key": RISK_KEY,
            "type": "json",
            "value": json.dumps(risk_payload),
        }
    }

    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=20.0, write=10.0, connect=10.0)) as client:
        resp = await client.post(url, json=body, headers=headers)
        if resp.status_code not in (200, 201):
            text = resp.text[:500]
            logger.warning(
                f"[{shop_domain}] metafield write failed for order {order_id} "
                f"status={resp.status_code} body={text}"
            )
            raise HTTPException(status_code=502, detail="Metafield write failed")
        return resp.json()


@router.post("/orders-create")
async def orders_create(request: Request, db: Session = Depends(get_db)):
    # --- Verify webhook ---
    raw = await request.body()
    header_hmac = request.headers.get("x-shopify-hmac-sha256")
    topic = request.headers.get("x-shopify-topic", "orders/create")
    shop_domain = request.headers.get("x-shopify-shop-domain", "unknown")

    if not header_hmac or not verify_shopify_hmac(raw, header_hmac, settings.SHOPIFY_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    # --- Parse payload & idempotency ---
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Use Shopify order ID for idempotency (falls back to other identifiers)
    event_id = str(
        payload.get("id")
        or payload.get("order_number")
        or payload.get("admin_graphql_api_id")
        or ""
    )
    if event_id and is_processed(db, event_id):
        return {"ok": True, "idempotent": True}

    # --- Minimal fields used downstream ---
    order_id = payload.get("id")
    email = (payload.get("email") or "").strip().lower() if payload.get("email") else None
    source_ip = (payload.get("client_details") or {}).get("browser_ip") or payload.get("browser_ip")
    total_price = payload.get("total_price")
    currency = payload.get("currency")

    # --- Query Risk Vault (anonymized identifiers) ---
    join_ids = {"email": email, "device_id": None, "ip": source_ip}
    q = QueryInput(shop_id=shop_domain, ids=join_ids)
    vault_result = await run_in_threadpool(query_core, q, db)

    # --- Compute hybrid score (rules + vault + any external adapters if present) ---

    
    # compute_risk is assumed to return: {"score": int, "verdict": str, "reasons": [str], "evidence": {...}}
    risk = compute_risk(
        order_payload=payload,
        vault=vault_result.model_dump() if hasattr(vault_result, "model_dump") else vault_result,
        context={"total_price": total_price, "currency": currency, "source_ip": source_ip},
    )

    # Normalize risk output
    score = int(risk.get("score", 0))
    verdict = str(risk.get("verdict", "green"))
    reasons = list(risk.get("reasons", []))

    # --- Write metafield back to Shopify (best-effort; fail with 502 if Shopify rejects) ---
    # You should pull a **shop-specific** access token from your store/session db.
    # For simplicity this uses a global token from settings; swap to per-shop lookup in production.
    admin_token = getattr(settings, "SHOPIFY_ADMIN_TOKEN", None)
    if not admin_token:
        logger.warning(f"[{shop_domain}] SHOPIFY_ADMIN_TOKEN not configured; skipping metafield write")
    else:
        risk_payload = {
            "score": score,
            "verdict": verdict,
            "reasons": reasons,
            # include a tiny evidence slice that’s safe to expose to merchants
            "evidence": (risk.get("evidence") or {}),
        }
        if not order_id:
            logger.warning(f"[{shop_domain}] Missing numeric order id; skipping metafield write")
        else:
            await write_order_risk_metafield(
                shop_domain=shop_domain,
                order_id=order_id,
                token=admin_token,
                risk_payload=risk_payload,
            )

    # --- Log + idempotency mark ---
    logger.info(
        f"[{shop_domain}] order {event_id or order_id} verdict={verdict} score={score} reasons={reasons}"
    )
    if event_id:
        mark_processed(db, topic, event_id)

    return {"ok": True, "verdict": verdict, "score": score, "reasons": reasons}
