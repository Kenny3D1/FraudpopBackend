\
import hashlib, secrets

def normalize_value(id_type: str, value: str) -> str:
    """
    Normalize identifier values prior to hashing.
    - email: lowercase + trim
    """
    if value is None:
        return ""
    v = value.strip()
    if id_type == "email":
        v = v.lower()
    return v

def hash_identifier(id_type: str, value: str, shop_id: str, pepper: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """
    Returns (id_hash, salt). Uses SHA-256 over:
      pepper || shop_id || normalized_value || salt
    """
    if not value:
        return b"", b""
    if salt is None:
        salt = secrets.token_bytes(16)
    norm = normalize_value(id_type, value)
    h = hashlib.sha256()
    h.update(pepper.encode("utf-8"))
    h.update(shop_id.encode("utf-8"))
    h.update(norm.encode("utf-8"))
    h.update(salt)
    return h.digest(), salt
