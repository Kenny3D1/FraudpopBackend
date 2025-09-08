import hmac, hashlib, base64

def verify_shopify_hmac(raw_body: bytes, header_hmac_base64: str, secret: str) -> bool:
    digest = hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode('utf-8')
    return hmac.compare_digest(expected, header_hmac_base64 or "")
