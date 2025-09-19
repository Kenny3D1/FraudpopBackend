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

MYSHOPIFY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\.myshopify\.com$", re.I)

def normalize_shop_domain(shop: str) -> str:
    s = (shop or "").strip().lower()
    if not MYSHOPIFY_RE.match(s):
        raise ValueError(f"Invalid shop domain: {s!r}")
    return s

def to_order_gid(order_id_or_gid) -> str:
    s = str(order_id_or_gid)
    return s if s.startswith("gid://") else f"gid://shopify/Order/{int(s)}"

def extract_note_attr(order: dict, key: str):
    na = order.get("note_attributes") or []
    if isinstance(na, list):
        for item in na:
            if isinstance(item, dict) and item.get("name") == key:
                return item.get("value")
    elif isinstance(na, dict):
        return na.get(key)  # fallback if you ever get dict shape
    return None

def metafields_set_via_remix(shop: str, order_id_or_gid, result: dict) -> None:
    shop = normalize_shop_domain(shop)
    owner_id = to_order_gid(order_id_or_gid)

    logger.info(
        "Writing metafields for order %s in shop %s (verdict=%s, score=%s)",
        owner_id, shop, result.get("verdict"), result.get("final_score")
    )

    variables = [{
        "ownerId": owner_id,
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
    url = urljoin(base + "/", "api/metafields-set")

    payload = {"shop": shop, "metafields": variables}
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-internal-auth": INTERNAL_SHARED_SECRET,
        "User-Agent": "fraudpop-backend/1.0 (+requests)",
    }

    def _post_once():
        r = requests.post(url, headers=headers, json=payload, timeout=12, allow_redirects=False)
        if 300 <= r.status_code < 400:
            loc = r.headers.get("Location", "")
            raise RuntimeError(f"Unexpected redirect {r.status_code} to {loc} (POST {url})")
        try:
            r.raise_for_status()
        except requests.HTTPError:
            snippet = (r.text or "")[:1000]
            logger.error("metafieldsSet HTTP %s\nURL: %s\nCT: %s\nBody:\n%s",
                         r.status_code, r.url, r.headers.get("Content-Type"), snippet)
            raise
        ct = (r.headers.get("Content-Type") or "").lower()
        if "application/json" not in ct:
            snippet = (r.text or "")[:1000]
            raise RuntimeError(f"Non-JSON response ({ct or 'no content-type'}) from {r.url}:\n{snippet}")
        try:
            return r.json()
        except ValueError:
            snippet = (r.text or "")[:1000]
            raise RuntimeError(f"Invalid JSON from {r.url}:\n{snippet}")

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
            if (re.search(r"\b429\b", msg) or re.search(r"\bHTTP 5\d{2}\b", msg)) and attempt < 2:
                sleep = 1.5 * (attempt + 1)
                logger.warning("Retrying metafieldsSet in %.1fs due to: %s", sleep, msg)
                time.sleep(sleep)
                continue
            raise
# ---------- deterministic lookup key for velocity counting ----------
def lookup_key(value: str, pepper: str = "fraudpop_pepper_v1") -> str:
    return hashlib.sha256((pepper + value).encode("utf-8")).hexdigest()


@celery.task(name="ping")
def ping():
    logger.info("ping received")
    return "pong"

@celery.task(name="process_order_async", autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def process_order_async(shop_id: str, order: dict):
    shop_domain = normalize_shop_domain(shop_id)
    order_id_str = str(order.get("id"))
    order_gid = order.get("admin_graphql_api_id") or order_id_str

    data = {
        "shop_id": shop_domain,
        "order_id": order_id_str,
        "total_price": float(order.get("total_price", 0) or 0),
        "currency": order.get("currency"),
        "email": (order.get("email") or "").lower(),
        "ip": (order.get("client_details") or {}).get("browser_ip"),
        "country": (order.get("shipping_address") or {}).get("country_code"),
        "billing_country": (order.get("billing_address") or {}).get("country_code"),
        "shipping_country": (order.get("shipping_address") or {}).get("country_code"),
        "device_id": extract_note_attr(order, "fraudpop_device_id"),
        "repeat_email": 0,
        "repeat_ip": 0,
        "repeat_device": 0,
    }

    logger.info("Processing order %s for shop %s", data["order_id"], shop_domain)

    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        try:
            if data["email"]:
                k = lookup_key(data["email"])
                row = db.execute(
                    select(RiskIdentity).where(RiskIdentity.kind=="email", RiskIdentity.hash==k)
                ).scalar_one_or_none()
                if row: data["repeat_email"] = row.seen_count

            if data["ip"]:
                k = lookup_key(data["ip"])
                row = db.execute(
                    select(RiskIdentity).where(RiskIdentity.kind=="ip", RiskIdentity.hash==k)
                ).scalar_one_or_none()
                if row: data["repeat_ip"] = row.seen_count

            if data["device_id"]:
                k = lookup_key(data["device_id"])
                row = db.execute(
                    select(RiskIdentity).where(RiskIdentity.kind=="device", RiskIdentity.hash==k)
                ).scalar_one_or_none()
                if row: data["repeat_device"] = row.seen_count

            result = defender3d(data)
            logger.info("Order %s scored %s (%s)", data["order_id"], result["final_score"], result["verdict"])

            rec = OrderRisk(
                shop_id=shop_domain,
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
                shop_id=shop_domain,
                event_id=(order.get("admin_graphql_api_id") or "none"),
            ).first()
            if wh: wh.processed = True

            db.commit()
        except Exception:
            db.rollback()
            raise

    try:
        metafields_set_via_remix(shop_domain, order_gid, result)
        logger.info("Metafields written successfully for order %s", order_id_str)
    except Exception:
        logger.exception("Metafield write failed")
        pass

    return {"ok": True, "order_id": data["order_id"], "score": result["final_score"], "verdict": result["verdict"]}
