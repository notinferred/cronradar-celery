"""
CronRadar Celery Integration

Automatic monitoring for Celery periodic tasks.
Supports Selective mode (opt-in) and MonitorAll mode (comprehensive monitoring).
"""

import sys
from typing import Optional
from celery import Celery
from celery.signals import task_success, task_failure, task_retry

from .monitors import setup_task_monitoring, monitor_decorator, skip_monitor_decorator
from .discovery import discover_and_sync_tasks

__version__ = "0.0.1"

# Track initialization to prevent duplicate setup
_initialized = False
_selective_mode = True


def setup_cronradar(app: Celery, mode: str = 'selective', api_key: Optional[str] = None) -> None:
    """
    Configure CronRadar monitoring for Celery tasks.

    Args:
        app: Celery application instance
        mode: 'selective' (monitor tasks with @monitor) or 'all' (monitor all periodic tasks)
        api_key: Optional API key (defaults to CRONRADAR_API_KEY env var)

    Example:
        from celery import Celery
        from cronradar_celery import setup_cronradar

        app = Celery('myapp')
        setup_cronradar(app, mode='all')
    """
    global _initialized, _selective_mode

    if _initialized:
        print("[CronRadar.Celery] Already initialized. Skipping duplicate setup.", file=sys.stderr)
        return

    _initialized = True
    _selective_mode = (mode == 'selective')

    # Store API key in environment if provided
    if api_key:
        import os
        os.environ['CRONRADAR_API_KEY'] = api_key

    mode_desc = "selective (opt-in)" if _selective_mode else "monitorAll (opt-out)"
    print(f"[CronRadar.Celery] Initializing in {mode_desc} mode", file=sys.stderr)

    # Setup task monitoring via signals
    setup_task_monitoring(app, _selective_mode)

    # Auto-discover and sync beat schedule tasks
    discover_and_sync_tasks(app, _selective_mode)

    print("[CronRadar.Celery] ✓ Monitoring enabled successfully!", file=sys.stderr)


# Decorators for selective mode
monitor = monitor_decorator
skip_monitor = skip_monitor_decorator


__all__ = ['setup_cronradar', 'monitor', 'skip_monitor', '__version__']
