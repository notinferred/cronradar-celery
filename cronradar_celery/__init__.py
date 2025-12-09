"""
CronRadar Celery Integration

Automatic monitoring for Celery periodic tasks.
Monitors all tasks by default - use @skip_monitor to opt-out.
"""

import sys
from typing import Optional
from celery import Celery
from celery.signals import task_success, task_failure, task_retry

from .monitors import setup_task_monitoring, skip_monitor_decorator
from .discovery import discover_and_sync_tasks

__version__ = "0.0.3"

# Track initialization to prevent duplicate setup
_initialized = False


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
    global _initialized

    if _initialized:
        print("[CronRadar.Celery] Already initialized. Skipping duplicate setup.", file=sys.stderr)
        return

    _initialized = True

    # Store API key in environment if provided
    if api_key:
        import os
        os.environ['CRONRADAR_API_KEY'] = api_key

    print("[CronRadar.Celery] Initializing MonitorAll mode - use @skip_monitor to opt-out", file=sys.stderr)

    # Setup task monitoring via signals
    setup_task_monitoring(app)

    # Auto-discover and sync beat schedule tasks
    discover_and_sync_tasks(app)

    print("[CronRadar.Celery] ✓ Monitoring enabled successfully!", file=sys.stderr)


# Decorator for opting out
skip_monitor = skip_monitor_decorator


__all__ = ['setup_cronradar', 'skip_monitor', '__version__']
