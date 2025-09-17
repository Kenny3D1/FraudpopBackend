# app/shopify_oauth.py
import hmac, hashlib, secrets, urllib.parse, requests
from fastapi import HTTPException, Request
from ..config import settings
from ..database import SessionLocal
from ..models import Shop

def _nonce() -> str:
    return secrets.token_urlsafe(24)

def _sign_ok(query: dict) -> bool:
    """
    Verify Shopify callback HMAC.
    Shopify signs all query params except hmac itself; order is lexicographic.
    """
    if "hmac" not in query:
        return False
    h = query["hmac"]
    items = [(k, v) for k, v in query.items() if k != "hmac"]
    items.sort(key=lambda x: x[0])
    msg = "&".join([f"{k}={v}" for k, v in items]).encode("utf-8")
    digest = hmac.new(
        settings.SHOPIFY_API_SECRET.get_secret_value().encode("utf-8"),
        msg,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(digest, h)

def build_install_url(shop: str, state: str) -> str:
    """
    Offline access: DO NOT include grant_options[]=per-user
    """
    base = f"https://{shop}/admin/oauth/authorize"
    params = {
        "client_id": settings.SHOPIFY_API_KEY,
        "scope": settings.SHOPIFY_SCOPES,
        "redirect_uri": f"{settings.APP_URL}/auth/callback",
        "state": state,
    }
    return f"{base}?{urllib.parse.urlencode(params)}"

def exchange_token(shop: str, code: str) -> dict:
    """
    POST /admin/oauth/access_token to get offline token.
    (Offline tokens don’t expire; no refresh.)
    """
    url = f"https://{shop}/admin/oauth/access_token"
    payload = {
        "client_id": settings.SHOPIFY_API_KEY,
        "client_secret": settings.SHOPIFY_API_SECRET.get_secret_value(),
        "code": code,
    }
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()
    return r.json()  # {access_token, scope}
