
from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime

# Only keep schemas used in backend endpoints
class ObserveInput(BaseModel):
    shop_id: str
    ids: Dict[str, Optional[str]]
    outcome: Dict[str, int] = Field(default_factory=dict)

class QueryInput(BaseModel):
    shop_id: str
    ids: Dict[str, Optional[str]]

class QueryResponse(BaseModel):
    signals: Dict[str, dict]
    vault_verdict: str
    reasons: list[str]

class CaptureInput(BaseModel):
    shop_id: str
    session_id: str
    device_id: Optional[str] = None
    cart_token: Optional[str] = None
    email: Optional[str] = None
