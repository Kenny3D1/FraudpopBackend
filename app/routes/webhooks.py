from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db, Base, engine
from ..utils.shopify import verify_shopify_hmac
from ..utils.idempotency import is_processed, mark_processed
from ..config import settings
from ..schemas import QueryInput
from .vault import query as vault_query
import json

router = APIRouter(prefix="/webhooks", tags=["shopify"])
Base.metadata.create_all(bind=engine)

@router.post("/orders-create")
async def orders_create(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    header_hmac = request.headers.get("x-shopify-hmac-sha256")
    topic = request.headers.get("x-shopify-topic", "orders/create")
    shop_domain = request.headers.get("x-shopify-shop-domain", "unknown")

    if not verify_shopify_hmac(raw, header_hmac, settings.SHOPIFY_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    payload = json.loads(raw.decode("utf-8"))
    event_id = str(payload.get("id") or payload.get("order_number") or payload.get("admin_graphql_api_id") or "")
    if event_id and is_processed(db, event_id):
        return {"ok": True, "idempotent": True}

    email = (payload.get("email") or "").strip().lower() if payload.get("email") else None
    join_ids = {"email": email, "device_id": None, "ip": None}
    q = QueryInput(shop_id=shop_domain, ids=join_ids)
    vault_result = await vault_query(q, db)

    # TODO: write back metafield via Shopify Admin API
    from ..utils.logging import logger
    logger.info(f"[{shop_domain}] order {event_id} vault={vault_result.vault_verdict} reasons={vault_result.reasons}")

    if event_id:
        mark_processed(db, topic, event_id)

    return {"ok": True, "verdict": vault_result.vault_verdict, "reasons": vault_result.reasons}
