from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db, Base, engine
from ..schemas import CaptureInput
from ..models import DeviceCapture

router = APIRouter(prefix="/v1", tags=["capture"])

Base.metadata.create_all(bind=engine)

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
