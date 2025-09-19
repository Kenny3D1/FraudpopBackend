import os, time, json, requests, hashlib, re
from celery import Celery
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_sessionmaker
from app.models import OrderRisk, EvidenceLog, WebhookEvent, RiskIdentity
from app.rules.defender3d import defender3d
from app.utils.logging import logger
from urllib.parse import urljoin

REDIS_URL = settings.REDIS_URL

celery = Celery("fraudpop", broker=REDIS_URL, backend=REDIS_URL)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
)

SHOPIFY_API_VERSION = "2025-01"

REMIX_URL = settings.REMIX_URL
INTERNAL_SHARED_SECRET = settings.INTERNAL_SHARED_SECRET

def metafields_set_via_remix(shop: str, order_id: int, result: dict) -> None:
    logger.info(
        "Writing metafields for order %s in shop %s (verdict=%s, score=%s)",
        order_id, shop, result.get("verdict"), result.get("final_score")
    )

    variables = [{
        "ownerId": f"gid://shopify/Order/{order_id}",
        "namespace": "fraudpop",
        "key": "risk",
        "type": "json",
        "value": json.dumps({
            "score": result["final_score"],
            "rules_score": result["rules_score"],
            "verdict": result["verdict"],
            "reasons": result["reasons"],
        }),
    }]

    base = (REMIX_URL or "").strip().rstrip("/")
    url = urljoin(base + "/", "internal/metafields-set")

    payload = {"shop": (shop or "").strip().lower(), "metafields": variables}
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-internal-auth": INTERNAL_SHARED_SECRET,
        # Optional but helpful for some CDNs/WAFs:
        "User-Agent": "fraudpop-backend/1.0 (+requests)",
    }

    def _post_once():
        # Do NOT follow redirects; expose them explicitly
        r = requests.post(url, headers=headers, json=payload, timeout=12, allow_redirects=False)

        # Surface redirects clearly (common cause of HTML/empty)
        if 300 <= r.status_code < 400:
            loc = r.headers.get("Location", "")
            raise RuntimeError(f"Unexpected redirect {r.status_code} to {loc} (POST {url})")

        # HTTP error with body snippet
        try:
            r.raise_for_status()
        except requests.HTTPError:
            snippet = (r.text or "")[:1000]
            logger.error("metafieldsSet HTTP %s\nURL: %s\nCT: %s\nBody:\n%s",
                         r.status_code, r.url, r.headers.get("Content-Type"), snippet)
            raise

        # Must be JSON; otherwise log snippet and fail
        ct = (r.headers.get("Content-Type") or "").lower()
        if "application/json" not in ct:
            snippet = (r.text or "")[:1000]
            raise RuntimeError(f"Non-JSON response ({ct or 'no content-type'}) from {r.url}:\n{snippet}")

        try:
            return r.json()
        except ValueError:
            snippet = (r.text or "")[:1000]
            raise RuntimeError(f"Invalid JSON from {r.url}:\n{snippet}")

    # tiny rate-limit/5xx retry
    for attempt in range(3):
        try:
            data = _post_once()
            if not data.get("ok"):
                logger.error("metafieldsSet failed JSON: %s", data)
                raise RuntimeError(f"metafieldsSet failed: {data}")
            logger.info("metafieldsSet success: %s", data)
            return
        except RuntimeError as e:
            msg = str(e)
            # retry only on rate limit or 5xx hints
            if (re.search(r"\b429\b", msg) or re.search(r"\bHTTP 5\d{2}\b", msg)) and attempt < 2:
                sleep = 1.5 * (attempt + 1)
                logger.warning("Retrying metafieldsSet in %.1fs due to: %s", sleep, msg)
                time.sleep(sleep)
                continue
            # no more retries; rethrow
            raise

# ---------- deterministic lookup key for velocity counting ----------
def lookup_key(value: str, pepper: str = "fraudpop_pepper_v1") -> str:
    return hashlib.sha256((pepper + value).encode("utf-8")).hexdigest()


@celery.task(name="ping")
def ping():
    logger.info("ping received")
    return "pong"

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
    logger.info(f"Processing order {data['order_id']} for shop {shop_id}")

    SessionLocal = get_sessionmaker()
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
        logger.info(f"Order {data['order_id']} scored {result['final_score']} ({result['verdict']})")

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
        metafields_set_via_remix(shop_id, int(order["id"]), result)
        logger.info(f"Metafields written successfully for order {order.get('id')}")
    except Exception:
        # log and continue; don’t fail the whole task
        logger.exception("Metafield write failed")
        pass

    return {"ok": True, "order_id": data["order_id"], "score": result["final_score"], "verdict": result["verdict"]}
