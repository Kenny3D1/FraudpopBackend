from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from ..models import OrderRisk, EvidenceLog
from ..database import get_db, Base, engine, SessionLocal
from ..schemas import CaptureInput
from ..models import DeviceCapture


router = APIRouter(prefix="/v1", tags=["capture"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@router.get("/orders")
def list_orders(db: Session = Depends(get_db),
                verdict: str | None = Query(None),
                q: str | None = Query(None),
                limit: int = 50):
    stmt = select(OrderRisk).order_by(desc(OrderRisk.id)).limit(limit)
    if verdict: stmt = stmt.where(OrderRisk.verdict==verdict)
    rows = db.execute(stmt).scalars().all()
    return [{"order_id": r.order_id, "score": r.score, "rules_score": r.rules_score,
             "verdict": r.verdict, "reasons": r.reasons, "currency": r.currency,
             "total_price": r.total_price, "created_at": r.created_at} for r in rows]

@router.get("/orders/{order_id}/evidence")
def order_evidence(order_id: str, db: Session = Depends(get_db)):
    rows = db.execute(select(EvidenceLog).where(EvidenceLog.order_id==order_id)
                      .order_by(EvidenceLog.id)).scalars().all()
    return [{"key": r.key, "value": r.value, "created_at": r.created_at} for r in rows]


@router.post("/capture")
def capture(payload: CaptureInput, db: Session = Depends(get_db)):
    rec = DeviceCapture(
        shop_id=payload.shop_id,
        session_id=payload.session_id,
        device_id=payload.device_id,
        cart_token=payload.cart_token,
        email=payload.email
    )
    db.add(rec)
    db.commit()
    return {"ok": True}

