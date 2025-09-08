from sqlalchemy.orm import Session
from sqlalchemy import select
from ..models import WebhookEvent

def is_processed(db: Session, event_id: str) -> bool:
    q = select(WebhookEvent).where(WebhookEvent.event_id == event_id)
    row = db.execute(q).scalar_one_or_none()
    return row is not None

def mark_processed(db: Session, topic: str, event_id: str) -> None:
    evt = WebhookEvent(topic=topic, event_id=event_id)
    db.add(evt)
    db.commit()
