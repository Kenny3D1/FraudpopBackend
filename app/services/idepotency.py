# app/services/idempotency.py
from contextlib import contextmanager
from sqlalchemy import select
from app.db import get_db
from app.models import WebhookEvent
from datetime import datetime, timezone

@contextmanager
def ensure_once(topic: str, event_id: str | None, shop_id: str):
    db = next(get_db())
    do_process = True
    if not event_id:
        # fallback: still allow processing but log as non-idempotent
        event_id = f"{topic}-noid-{datetime.now(timezone.utc).timestamp()}"
    existing = db.execute(
        select(WebhookEvent).where(WebhookEvent.event_id == event_id)
    ).scalar_one_or_none()
    if existing:
        do_process = False
    else:
        db.add(WebhookEvent(topic=topic, event_id=event_id, shop_id=shop_id))
        db.commit()
    class Once:
        do_process = do_process
        def mark_processed(self):
            ev = db.execute(
                select(WebhookEvent).where(WebhookEvent.event_id == event_id)
            ).scalar_one()
            ev.processed_at = datetime.now(timezone.utc)
            ev.status = "processed"
            db.commit()
    try:
        yield Once()
    finally:
        db.close()
