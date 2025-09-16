
import json
import requests
from celery import Celery
from sqlalchemy.orm import Session
from .config import settings
from .database import SessionLocal
from .models import OrderRisk, EvidenceLog, WebhookEvent
from app.rules.defender3d import defender3d

celery = Celery("fraudpop", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

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

    # Use context manager for DB session
    db = SessionLocal()
    try:
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

    # Write back metafield (MVP: private app token; later: app proxy or offline token)
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
