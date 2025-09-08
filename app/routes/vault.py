from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..database import get_db, Base, engine
from ..schemas import ObserveInput, QueryInput, QueryResponse, VaultSignal
from ..models import Observation
from ..hashing import hash_identifier
from ..config import settings
from datetime import datetime

router = APIRouter(prefix="/vault", tags=["vault"])

Base.metadata.create_all(bind=engine)

def _merge_outcomes(old: dict, new: dict) -> dict:
    out = dict(old or {})
    for k, v in (new or {}).items():
        out[k] = int(out.get(k, 0)) + int(v or 0)
    return out

@router.post("/observe")
def observe(payload: ObserveInput, db: Session = Depends(get_db)):
    for k in ["email","device_id","ip","phone"]:
        val = (payload.ids or {}).get(k)
        if not val:
            continue
        id_type = "device" if k == "device_id" else k
        h, salt = hash_identifier(id_type, val, payload.shop_id, settings.VAULT_PEPPER)
        row = db.execute(select(Observation).where(Observation.id_type==id_type, Observation.id_hash==h)).scalar_one_or_none()
        if row:
            row.seen_count += 1
            row.last_seen = datetime.utcnow()
            row.outcomes = _merge_outcomes(row.outcomes, payload.outcome)
        else:
            row = Observation(
                shop_id=payload.shop_id,
                id_type=id_type,
                id_hash=h,
                salt=salt,
                seen_count=1,
                outcomes=payload.outcome or {}
            )
            db.add(row)
        db.commit()
    return {"ok": True}

@router.post("/query", response_model=QueryResponse)
def query(payload: QueryInput, db: Session = Depends(get_db)):
    results: dict[str, VaultSignal] = {}
    reasons: list[str] = []
    verdict = "green"

    def update_verdict(sig: VaultSignal, id_type: str):
        nonlocal verdict, reasons
        chb = int((sig.outcomes or {}).get("chargebacks", 0))
        if chb >= 1:
            verdict = "red"
            reasons.append(f"{id_type} seen with prior chargeback")
        elif sig.seen_count >= 10 and verdict != "red":
            verdict = "warn"
            reasons.append(f"{id_type} seen frequently across network")

    for k in ["email","device_id","ip","phone"]:
        val = (payload.ids or {}).get(k)
        id_type = "device" if k == "device_id" else k
        if not val:
            continue
        h, _ = hash_identifier(id_type, val, payload.shop_id, settings.VAULT_PEPPER, salt=b"")  # deterministic check
        row = db.execute(select(Observation).where(Observation.id_type==id_type, Observation.id_hash==h)).scalar_one_or_none()
        if row:
            sig = VaultSignal(seen_count=row.seen_count, outcomes=row.outcomes, last_seen=row.last_seen)
            results[id_type] = sig
            update_verdict(sig, id_type)

    return QueryResponse(signals=results, vault_verdict=verdict, reasons=list(set(reasons)))
