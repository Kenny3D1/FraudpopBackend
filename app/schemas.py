from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime

class ObserveInput(BaseModel):
    shop_id: str
    ids: Dict[str, Optional[str]]
    outcome: Dict[str, int] = Field(default_factory=dict)

class VaultSignal(BaseModel):
    seen_count: int = 0
    outcomes: Dict[str, int] = Field(default_factory=dict)
    last_seen: Optional[datetime] = None

class QueryInput(BaseModel):
    shop_id: str
    ids: Dict[str, Optional[str]]

class QueryResponse(BaseModel):
    signals: Dict[str, VaultSignal]
    vault_verdict: str
    reasons: list[str]

class CaptureInput(BaseModel):
    shop_id: str
    session_id: str
    device_id: Optional[str] = None
    cart_token: Optional[str] = None
    email: Optional[str] = None
