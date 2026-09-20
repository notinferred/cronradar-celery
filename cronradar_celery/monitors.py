"""
Task monitoring via Celery signals.
"""

import sys
from functools import wraps
from typing import Any, Callable
from celery import Celery
from celery.signals import task_prerun, task_success, task_failure

import cronradar
from .utils import normalize_task_name

RECONCILE_TASK_NAME = "cronradar_celery.reconcile"


def _belongs_to_app(task, app: Celery) -> bool:
    return (task is not None and getattr(task, 'app', None) is app
            and getattr(task, 'name', None) != RECONCILE_TASK_NAME)


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
    Setup Celery signal handlers for task monitoring with lifecycle tracking.
    Monitors all tasks unless they have @skip_monitor decorator.

    Args:
        app: Celery application instance
    """
    if getattr(app, '_cronradar_monitoring_registered', False) is True:
        return

    # These receivers are local functions. Weak references would let garbage
    # collection silently remove execution reporting after setup returns.
    @task_prerun.connect(weak=False)
    def handle_task_prerun(sender=None, task_id=None, task=None, **kwargs):
        """
        Handle task start for lifecycle tracking.
        Monitors all tasks unless marked with @skip_monitor.
        """
        try:
            # Get task name
            task_name = None
            if task and hasattr(task, 'name'):
                task_name = task.name
            elif sender and hasattr(sender, 'name'):
                task_name = sender.name

            if not task_name:
                return

            # Check if this task should be monitored
            task_obj = task or sender
            if not _belongs_to_app(task_obj, app) or not should_monitor_task(task_obj):
                return

            # Normalize task name to monitor key
            monitor_key = normalize_task_name(task_name)

            if not monitor_key:
                return

            # Signal job start for lifecycle tracking
            cronradar.start_job(monitor_key)

        except Exception as e:
            # Never break user's task execution
            print(f"[CronRadar.Celery] StartJob error: {e}", file=sys.stderr)

    @task_success.connect(weak=False)
    def handle_task_success(sender=None, **kwargs):
        """
        Handle successful task completion for lifecycle tracking.
        Monitors all tasks unless marked with @skip_monitor.
        """
        try:
            # Get task name from sender
            if not sender or not hasattr(sender, 'name'):
                return

            task_name = sender.name

            # Check if this task should be monitored
            if not _belongs_to_app(sender, app) or not should_monitor_task(sender):
                return

            # Normalize task name to monitor key
            monitor_key = normalize_task_name(task_name)

            if not monitor_key:
                return

            # Signal job completion for lifecycle tracking
            cronradar.complete_job(monitor_key)

        except Exception as e:
            # Never break user's task execution
            print(f"[CronRadar.Celery] CompleteJob error: {e}", file=sys.stderr)

    @task_failure.connect(weak=False)
    def handle_task_failure(sender=None, task_id=None, exception=None, **kwargs):
        """
        Handle task failure for immediate failure reporting.
        Monitors all tasks unless marked with @skip_monitor.
        """
        try:
            # Get task name from sender
            if not sender or not hasattr(sender, 'name'):
                return

            task_name = sender.name

            # Check if this task should be monitored
            if not _belongs_to_app(sender, app) or not should_monitor_task(sender):
                return

            # Normalize task name to monitor key
            monitor_key = normalize_task_name(task_name)

            if not monitor_key:
                return

            # Signal job failure for immediate alert
            message = str(exception) if exception else "Task failed"
            cronradar.fail_job(monitor_key, message)

        except Exception as e:
            # Never break user's task execution
            print(f"[CronRadar.Celery] FailJob error: {e}", file=sys.stderr)

    app._cronradar_signal_receivers = (
        (task_prerun, handle_task_prerun),
        (task_success, handle_task_success),
        (task_failure, handle_task_failure),
    )
    app._cronradar_monitoring_registered = True


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
