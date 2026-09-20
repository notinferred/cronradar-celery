"""
Auto-discovery of Celery Beat periodic tasks.
"""

import sys
from celery import Celery

import cronradar
from .utils import normalize_task_name, generate_readable_name, schedule_to_cron
from .monitors import should_monitor_task, RECONCILE_TASK_NAME


def discover_and_sync_tasks(app: Celery) -> None:
    """
    Discover Celery Beat periodic tasks and reconcile them to CronRadar in a single
    request (the authoritative set), so dead-man coverage exists before a task ever runs.
    Honors @skip_monitor. Safe to call repeatedly (idempotent) - also used as the heartbeat.

    Args:
        app: Celery application instance
    """
    try:
        beat_schedule = app.conf.beat_schedule

        if not beat_schedule:
            print("[CronRadar.Celery] No beat schedule configured. Skipping auto-discovery.", file=sys.stderr)
            return

        monitors = []

        for schedule_name, schedule_config in beat_schedule.items():
            try:
                task_name = schedule_config.get('task')
                schedule = schedule_config.get('schedule')

                if not task_name or not schedule:
                    continue

                # Never monitor our own reconcile heartbeat
                if task_name == RECONCILE_TASK_NAME:
                    continue

                # Honor @skip_monitor when the task is registered on this app
                task_obj = app.tasks.get(task_name)
                if task_obj is not None and not should_monitor_task(task_obj):
                    continue

                monitor_key = normalize_task_name(task_name)
                if not monitor_key:
                    continue

                cron_expression = schedule_to_cron(schedule)
                if not cron_expression:
                    print(f"[CronRadar.Celery] Skipping '{task_name}': Unable to convert schedule to cron", file=sys.stderr)
                    continue

                monitors.append({
                    'key': monitor_key,
                    'schedule': cron_expression,
                    'name': generate_readable_name(task_name),
                })

            except Exception as e:
                print(f"[CronRadar.Celery] Failed to prepare '{schedule_name}': {e}", file=sys.stderr)
                continue

        cronradar.sync_monitors(monitors, source='celery')

    except Exception as e:
        print(f"[CronRadar.Celery] Discovery error: {e}", file=sys.stderr)
        # Don't fail app startup on discovery errors
