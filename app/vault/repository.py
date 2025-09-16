# app/vault/repository.py
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from ..models import RiskIdentity

def bump_identity(db: Session, kind: str, hashed: str):
    row = db.execute(select(RiskIdentity).where(RiskIdentity.kind==kind,
                                               RiskIdentity.hash==hashed)).scalar_one_or_none()
    if row:
        db.execute(update(RiskIdentity)
                   .where(RiskIdentity.id==row.id)
                   .values(seen_count=row.seen_count+1))
    else:
        db.add(RiskIdentity(kind=kind, hash=hashed, seen_count=1))
