import json
import time
import hashlib
import requests
from celery import Celery
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models import OrderRisk, EvidenceLog, WebhookEvent, RiskIdentity, Shop
from app.rules.defender3d import defender3d

celery = Celery("fraudpop", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

SHOPIFY_API_VERSION = "2025-01"

# ---------- deterministic lookup key for velocity counting ----------
def lookup_key(value: str, pepper: str = "fraudpop_pepper_v1") -> str:
    return hashlib.sha256((pepper + value).encode("utf-8")).hexdigest()

# ---------- OAuth token fetch (replace with your real implementation) ----------
def get_shop_token(db: Session, shop_domain: str) -> str:
    row = db.query(Shop).filter(Shop.shop_domain == shop_domain).one_or_none()
    if not row:
        raise RuntimeError(f"No token for shop {shop_domain}. Is the app installed?")
    return row.access_token

# ---------- GraphQL write (no Definition needed) ----------
def write_order_risk_metafield_gql(shop_id: str, token: str, order_id: int, payload: dict):
    url = f"https://{shop_id}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    owner_gid = f"gid://shopify/Order/{order_id}"

    mutation = """
    mutation SetRisk($metafields: [MetafieldsSetInput!]!) {
      metafieldsSet(metafields: $metafields) {
        metafields { id key namespace type value }
        userErrors { field message code }
      }
    }"""

    variables = {
      "metafields": [{
        "ownerId": owner_gid,
        "namespace": "fraudpop",
        "key": "risk",
        "type": "json",
        "value": json.dumps({
          "score": payload["final_score"],
          "rules_score": payload["rules_score"],
          "verdict": payload["verdict"],
          "reasons": payload["reasons"],
        })
      }]
    }

    # simple retry for rate limit
    for attempt in range(3):
        r = requests.post(
            url,
            headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
            json={"query": mutation, "variables": variables},
            timeout=8
        )
        if r.status_code == 429 and attempt < 2:
            time.sleep(1.5 * (attempt + 1))
            continue
        r.raise_for_status()
        data = r.json()
        errs = data.get("data", {}).get("metafieldsSet", {}).get("userErrors", [])
        if errs:
            # common issues: wrong ownerId type, missing scope, type mismatch
            raise RuntimeError(f"metafieldsSet errors: {errs}")
        return

# ---------- Celery task ----------
@celery.task(name="process_order_async", autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def process_order_async(shop_id: str, order: dict):
    data = {
        "shop_id": shop_id,
        "order_id": str(order.get("id")),
        "total_price": float(order.get("total_price", 0) or 0),
        "currency": order.get("currency"),
        "email": (order.get("email") or "").lower(),
        "ip": (order.get("client_details") or {}).get("browser_ip"),
        "country": (order.get("shipping_address") or {}).get("country_code"),
        "billing_country": (order.get("billing_address") or {}).get("country_code"),
        "shipping_country": (order.get("shipping_address") or {}).get("country_code"),
        "device_id": (order.get("note_attributes") or {}).get("fraudpop_device_id"),
        "repeat_email": 0,
        "repeat_ip": 0,
        "repeat_device": 0,
    }

    db = SessionLocal()
    try:
        # velocity counts using deterministic lookup keys
        if data["email"]:
            k = lookup_key(data["email"])
            row = db.execute(select(RiskIdentity).where(RiskIdentity.kind=="email",
                                                        RiskIdentity.hash==k)).scalar_one_or_none()
            if row:
                data["repeat_email"] = row.seen_count
        if data["ip"]:
            k = lookup_key(data["ip"])
            row = db.execute(select(RiskIdentity).where(RiskIdentity.kind=="ip",
                                                        RiskIdentity.hash==k)).scalar_one_or_none()
            if row:
                data["repeat_ip"] = row.seen_count
        if data["device_id"]:
            k = lookup_key(data["device_id"])
            row = db.execute(select(RiskIdentity).where(RiskIdentity.kind=="device",
                                                        RiskIdentity.hash==k)).scalar_one_or_none()
            if row:
                data["repeat_device"] = row.seen_count

        result = defender3d(data)

        rec = OrderRisk(
            shop_id=shop_id,
            order_id=data["order_id"],
            total_price=data["total_price"],
            currency=data["currency"],
            email=data["email"],
            ip=data["ip"],
            country=data["country"],
            score=result["final_score"],
            rules_score=result["rules_score"],
            verdict=result["verdict"],
            reasons=result["reasons"],
        )
        db.add(rec)
        db.add(EvidenceLog(order_id=data["order_id"], key="input", value=data))
        db.add(EvidenceLog(order_id=data["order_id"], key="scores", value=result))

        wh = db.query(WebhookEvent).filter_by(
            shop_id=shop_id,
            event_id=(order.get("admin_graphql_api_id") or "none")
        ).first()
        if wh:
            wh.processed = True

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # --- GraphQL writeback on the ORDER (no Definition needed) ---
    try:
        token = get_shop_token(shop_id)
        write_order_risk_metafield_gql(shop_id, token, int(order["id"]), result)
    except Exception:
        # log and continue; don’t fail the whole task
        # logger.exception("Metafield write failed")
        pass

    return {"ok": True, "order_id": data["order_id"], "score": result["final_score"], "verdict": result["verdict"]}
