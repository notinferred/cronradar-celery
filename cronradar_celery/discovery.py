"""
Auto-discovery of Celery Beat periodic tasks.
"""

import sys
from typing import Dict, Any
from celery import Celery

import cronradar
from .utils import normalize_task_name, generate_readable_name, schedule_to_cron


def discover_and_sync_tasks(app: Celery, selective_mode: bool) -> None:
    """
    Discover Celery Beat periodic tasks and sync them to CronRadar.

    Args:
        app: Celery application instance
        selective_mode: True for selective mode, False for monitorAll
    """
    try:
        # Get beat schedule configuration
        beat_schedule = app.conf.beat_schedule

        if not beat_schedule:
            print("[CronRadar.Celery] No beat schedule configured. Skipping auto-discovery.", file=sys.stderr)
            return

        print(f"[CronRadar.Celery] Discovering {len(beat_schedule)} periodic tasks...", file=sys.stderr)

        synced_count = 0

        for schedule_name, schedule_config in beat_schedule.items():
            try:
                # Extract task name and schedule
                task_name = schedule_config.get('task')
                schedule = schedule_config.get('schedule')

                if not task_name or not schedule:
                    continue

                # Check if this task should be monitored
                if selective_mode:
                    # In selective mode, check if task has @monitor decorator
                    # We can only check this at runtime, so we'll sync all and rely on
                    # the signal handler to filter. This ensures monitors exist for discovery.
                    # Alternative: Skip sync in selective mode and rely on self-healing
                    pass

                # Normalize task name to monitor key
                monitor_key = normalize_task_name(task_name)

                if not monitor_key:
                    continue

                # Convert schedule to cron expression
                cron_expression = schedule_to_cron(schedule)

                if not cron_expression:
                    print(f"[CronRadar.Celery] Skipping '{task_name}': Unable to convert schedule to cron", file=sys.stderr)
                    continue

                # Generate readable name
                readable_name = generate_readable_name(task_name)

                # Sync to CronRadar
                cronradar.sync_monitor(
                    monitor_key,
                    cron_expression,
                    source='celery',
                    name=readable_name
                )

                synced_count += 1

            except Exception as e:
                print(f"[CronRadar.Celery] Failed to sync '{schedule_name}': {e}", file=sys.stderr)
                continue

        if synced_count > 0:
            print(f"[CronRadar.Celery] ✓ Synced {synced_count} periodic tasks", file=sys.stderr)

    except Exception as e:
        print(f"[CronRadar.Celery] Discovery error: {e}", file=sys.stderr)
        # Don't fail app startup on discovery errors
