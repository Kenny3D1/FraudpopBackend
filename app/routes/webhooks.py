# app/webhooks.py

from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..utils.shopify import verify_shopify_hmac
from ..models import WebhookEvent
from sqlalchemy import select
from ..config import settings
from app.workers.tasks import process_order_async


router = APIRouter(prefix="/webhooks", tags=["webhooks"])

## Use shared get_db from database.py

@router.post("/orders-create")
async def orders_create(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    hmac_hdr = request.headers.get("X-Shopify-Hmac-Sha256", "")
    # Verify HMAC
    if not verify_shopify_hmac(raw, hmac_hdr):
        return {"ok": False, "error": "Invalid HMAC"}

    shop_id = request.headers.get("X-Shopify-Shop-Domain", "unknown")
    event_id = request.headers.get("X-Shopify-Webhook-Id", None)
    if not event_id:
        return {"ok": True, "error": "Missing event_id"}

    # Idempotency
    existing = db.execute(select(WebhookEvent).where(WebhookEvent.event_id==event_id)).scalar_one_or_none()
    if existing:
        return {"ok": True, "dedup": True}

    db.add(WebhookEvent(topic="orders/create", event_id=event_id))
    db.commit()

    payload = await request.json()
    # fire-and-forget Celery job
    process_order_async.delay(shop_id, payload)
    return {"ok": True}
