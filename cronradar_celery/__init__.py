"""
CronRadar Celery Integration

Automatic monitoring for Celery periodic tasks.
Monitors all tasks by default - use @skip_monitor to opt-out.
"""

import sys
from typing import Optional
from celery import Celery

from .monitors import setup_task_monitoring, skip_monitor_decorator
from .discovery import discover_and_sync_tasks, RECONCILE_TASK_NAME

__version__ = "0.1.1"

# How often the heartbeat re-declares the schedule (seconds).
RECONCILE_INTERVAL_SECONDS = 900

def setup_cronradar(app: Celery, api_key: Optional[str] = None) -> None:
    """
    Configure CronRadar monitoring for Celery tasks.
    Monitors all periodic tasks by default - use @skip_monitor decorator to opt-out.

    Args:
        app: Celery application instance
        api_key: Optional API key (defaults to CRONRADAR_API_KEY env var)

    Example:
        from celery import Celery
        from cronradar_celery import setup_cronradar

        app = Celery('myapp')
        setup_cronradar(app)
    """
    try:
        if getattr(app, '_cronradar_initialized', False) is True:
            return

        # The base SDK reads one process-wide key. Separate accounts should use
        # separate worker processes, as with CRONRADAR_API_KEY configuration.
        if api_key:
            import os
            os.environ['CRONRADAR_API_KEY'] = api_key

        setup_task_monitoring(app)
        _register_reconcile(app)
        discover_and_sync_tasks(app)
        app._cronradar_initialized = True
    except Exception as error:
        print(f"[CronRadar.Celery] Setup failed: {type(error).__name__}", file=sys.stderr)


def _register_reconcile(app: Celery) -> None:
    """
    Register the periodic reconcile task and add it to the beat schedule so the
    server keeps seeing the authoritative set (heartbeat) and drift is reflected.
    """
    try:
        @app.task(name=RECONCILE_TASK_NAME, shared=False)
        def _cronradar_reconcile():
            discover_and_sync_tasks(app)

        if app.conf.beat_schedule is None:
            app.conf.beat_schedule = {}

        app.conf.beat_schedule['cronradar-reconcile'] = {
            'task': RECONCILE_TASK_NAME,
            'schedule': float(RECONCILE_INTERVAL_SECONDS),
        }
    except Exception as e:
        print(f"[CronRadar.Celery] Failed to register reconcile heartbeat: {e}", file=sys.stderr)


# Decorator for opting out
skip_monitor = skip_monitor_decorator


__all__ = ['setup_cronradar', 'skip_monitor', '__version__']
