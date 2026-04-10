import os
from datetime import timedelta

from celery import Celery


def _redis_broker_url() -> str:
    raw = os.environ.get("REDIS_URL")
    if raw is None:
        return "redis://127.0.0.1:6379/0"
    u = str(raw).strip().strip('"').strip("'")
    if not u:
        return "redis://127.0.0.1:6379/0"
    return u


_redis = _redis_broker_url()

celery = Celery(
    "worker",
    broker=_redis,
    backend=_redis,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

import worker.tasks  # noqa: E402, F401 — registra tareas

from app.core.config import get_settings  # noqa: E402

_s = get_settings()
celery.conf.beat_schedule = {
    "hubspot-sync-and-smartlead-push": {
        "task": "worker.tasks.hubspot_sync_and_smartlead_push",
        "schedule": timedelta(seconds=_s.schedule_hubspot_sync_seconds),
    },
    "smartlead-active-stats-and-message-history": {
        "task": "worker.tasks.smartlead_active_stats_and_message_history",
        "schedule": timedelta(seconds=_s.schedule_smartlead_active_seconds),
    },
}
