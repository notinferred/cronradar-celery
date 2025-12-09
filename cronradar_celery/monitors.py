"""
Task monitoring via Celery signals.
"""

import sys
from functools import wraps
from typing import Any, Callable
from celery import Celery
from celery.signals import task_success

import cronradar
from .utils import normalize_task_name


def skip_monitor_decorator(func: Callable) -> Callable:
    """
    Mark a Celery task to skip monitoring in MonitorAll mode.

    Example:
        from cronradar_celery import skip_monitor

        @app.task
        @skip_monitor
        def internal_cleanup():
            pass
    """
    func._cronradar_skip = True
    return func


def setup_task_monitoring(app: Celery) -> None:
    """
    Setup Celery signal handlers for task monitoring.
    Monitors all tasks unless they have @skip_monitor decorator.

    Args:
        app: Celery application instance
    """

    @task_success.connect
    def handle_task_success(sender=None, **kwargs):
        """
        Handle successful task execution.
        Monitors all tasks unless marked with @skip_monitor.
        """
        try:
            # Get task name from sender
            if not sender or not hasattr(sender, 'name'):
                return

            task_name = sender.name

            # Check if this task should be monitored
            if not should_monitor_task(sender):
                return

            # Normalize task name to monitor key
            monitor_key = normalize_task_name(task_name)

            if not monitor_key:
                return

            # Use base SDK to monitor
            # Don't pass schedule here - it's already synced via discovery
            cronradar.monitor(monitor_key)

        except Exception as e:
            # Never break user's task execution
            print(f"[CronRadar.Celery] Monitor error: {e}", file=sys.stderr)


def should_monitor_task(task) -> bool:
    """
    Determine if a task should be monitored.
    Monitors all tasks unless marked with @skip_monitor decorator.

    Args:
        task: Celery task instance

    Returns:
        True if task should be monitored
    """
    try:
        # Get the actual task function
        task_func = None

        # Try to get the original function
        if hasattr(task, 'run'):
            task_func = task.run
        elif hasattr(task, '__wrapped__'):
            task_func = task.__wrapped__
        elif callable(task):
            task_func = task

        if not task_func:
            # If we can't determine, monitor by default
            return True

        # Monitor all tasks unless @skip_monitor decorator present
        return not getattr(task_func, '_cronradar_skip', False)

    except Exception as e:
        print(f"[CronRadar.Celery] Error checking task decorators: {e}", file=sys.stderr)
        # If we can't determine, monitor by default
        return True
