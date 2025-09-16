# tests/test_security.py
from app.security import verify_shopify_hmac
import pytest, hmac, hashlib

def test_webhook_hmac_ok():
    body = b'{"a":1}'
    secret = "shhh"
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    verify_shopify_hmac(body, sig, secret)  # no raise

def test_webhook_hmac_bad():
    with pytest.raises(Exception):
        verify_shopify_hmac(b"{}", "bad", "secret")
