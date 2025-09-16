
import json
import requests
from celery import Celery
from sqlalchemy.orm import Session
from ..config import settings
from ..database import SessionLocal
from ..models import OrderRisk, EvidenceLog, WebhookEvent

from app.rules.defender3d import defender3d
from app.vault.hasher import hash_identifier
from app.vault.repository import bump_identity

celery = Celery("fraudpop", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

@celery.task(name="write_order_risk_metafield")
def write_order_risk_metafield(shop_id: str, token: str, order_id: int, payload: dict):
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

    r = requests.post(
        url,
        headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
        json={"query": mutation, "variables": variables},
        timeout=8
    )
    r.raise_for_status()
    data = r.json()
    errs = data.get("data", {}).get("metafieldsSet", {}).get("userErrors", [])
    if errs:
        raise RuntimeError(f"metafieldsSet errors: {errs}")



@celery.task(name="process_order_async")
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
    }

    db = SessionLocal()
    try:
        # Hash and bump repeat counts in vault
        repeat_email = 0
        repeat_ip = 0
        repeat_device = 0
        if data["email"]:
            email_hash = hash_identifier(data["email"])
            bump_identity(db, "email", email_hash)
            # Query repeat count (simplified)
            from sqlalchemy import select
            from app.models import RiskIdentity
            row = db.execute(select(RiskIdentity).where(RiskIdentity.kind=="email", RiskIdentity.hash==email_hash)).scalar_one_or_none()
            if row:
                repeat_email = row.seen_count
        if data["ip"]:
            ip_hash = hash_identifier(data["ip"])
            bump_identity(db, "ip", ip_hash)
            row = db.execute(select(RiskIdentity).where(RiskIdentity.kind=="ip", RiskIdentity.hash==ip_hash)).scalar_one_or_none()
            if row:
                repeat_ip = row.seen_count
        if data["device_id"]:
            device_hash = hash_identifier(data["device_id"])
            bump_identity(db, "device", device_hash)
            row = db.execute(select(RiskIdentity).where(RiskIdentity.kind=="device", RiskIdentity.hash==device_hash)).scalar_one_or_none()
            if row:
                repeat_device = row.seen_count
        # Enrich order data for rules
        data["repeat_email"] = repeat_email
        data["repeat_ip"] = repeat_ip
        data["repeat_device"] = repeat_device

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
        wh = db.query(WebhookEvent).filter_by(shop_id=shop_id,
                                              event_id=(order.get("admin_graphql_api_id") or "none")).first()
        if wh:
            wh.processed = True
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

    metafield = {
        "metafield": {
            "namespace": "fraudpop",
            "key": "risk",
            "type": "json",
            "value": json.dumps({
                "score": result["final_score"],
                "rules_score": result["rules_score"],
                "verdict": result["verdict"],
                "reasons": result["reasons"]
            })
        }
    }
    # Uncomment and configure the following for production metafield writeback
    # try:
    #     requests.post(
    #         f"https://{shop_id}/admin/api/2025-01/metafields.json",
    #         headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
    #         json=metafield, timeout=8
    #     )
    # except Exception as e:
    #     # Log error or handle as needed
    #     pass


    return {"ok": True, "order_id": data["order_id"], "score": result["final_score"], "verdict": result["verdict"]}