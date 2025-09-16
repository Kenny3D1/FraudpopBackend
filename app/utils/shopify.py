import hmac, hashlib, base64, os

def verify_shopify_hmac(raw_body: bytes, header_hmac: str) -> bool:
    secret = os.environ["SHOPIFY_WEBHOOK_SECRET"].encode()
    digest = hmac.new(secret, raw_body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    # Timing-safe compare
    return hmac.compare_digest(expected, header_hmac)
