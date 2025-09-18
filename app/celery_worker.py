# app/celery_worker.py
import os
from celery import Celery
from .config import settings

REDIS_URL = settings.REDIS_URL

celery = Celery("fraudpop", broker=REDIS_URL, backend=REDIS_URL)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
)

# If your tasks live under app/workers/ (with __init__.py present)
celery.autodiscover_tasks(["app.workers"])