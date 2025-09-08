from celery import Celery
import os

CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BACKEND_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("fraudpop", broker=CELERY_BROKER_URL, backend=CELERY_BACKEND_URL)

@celery_app.task
def example_task(x, y):
    return x + y
