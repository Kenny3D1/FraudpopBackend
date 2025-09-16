# app/vault/hasher.py
from argon2 import PasswordHasher
from argon2.low_level import Type

_ph = PasswordHasher(
    time_cost=2, memory_cost=102400, parallelism=8, hash_len=32, type=Type.ID
)

def hash_identifier(value: str) -> str:
    # Store the full hash string (salt is embedded)
    return _ph.hash(value)
