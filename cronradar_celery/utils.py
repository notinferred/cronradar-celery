"""
Utility functions for Celery integration.
"""

import hashlib
import sys
import re
from typing import Optional
from datetime import timedelta

from cronradar.constants import MAX_MONITOR_KEY_LENGTH


def normalize_task_name(task_name: str) -> str:
    """
    Normalize Celery task name to CronRadar monitor key format.

    Examples:
        'myapp.tasks.send_email' -> 'myapp-tasks-send-email'
        'tasks.process_queue' -> 'tasks-process-queue'
    """
    if not task_name:
        return task_name

    # Replace dots and underscores with hyphens
    key = task_name.replace('.', '-').replace('_', '-')

    # Lowercase
    key = key.lower()

    # Remove any non-alphanumeric except hyphens
    key = re.sub(r'[^a-z0-9-]+', '-', key)

    # Remove leading/trailing hyphens
    key = key.strip('-')

    return shorten_monitor_key(key)


def shorten_monitor_key(key: str) -> str:
    """
    Shorten a normalized key over the monitor-key limit to a stable key, as every CronRadar SDK does
    for keys it derives: the first 91 characters without trailing hyphens, a hyphen, and the first 8
    hex characters of the SHA-256 of the full key (UTF-8). Keys within the limit are returned unchanged.
    """
    hash_length = 8
    if len(key) <= MAX_MONITOR_KEY_LENGTH:
        return key
    digest = hashlib.sha256(key.encode('utf-8')).hexdigest()[:hash_length]
    return key[:MAX_MONITOR_KEY_LENGTH - hash_length - 1].rstrip('-') + '-' + digest


def generate_readable_name(task_name: str) -> str:
    """
    Generate human-readable name from Celery task name.

    Examples:
        'myapp.tasks.send_email' -> 'Send Email'
        'tasks.process_queue' -> 'Process Queue'
    """
    if not task_name:
        return task_name

    # Take last part after final dot (the actual task name)
    parts = task_name.split('.')
    name = parts[-1] if parts else task_name

    # Convert snake_case to Title Case
    if '_' in name:
        return ' '.join(word.capitalize() for word in name.split('_'))

    # Convert camelCase to Title Case
    if name and name[0].islower() and any(c.isupper() for c in name):
        result = re.sub(r'([A-Z])', r' \1', name)
        return result.strip().title()

    # Default: capitalize first letter
    return name.capitalize()


def crontab_to_cron(crontab_obj) -> Optional[str]:
    """
    Convert a Celery crontab schedule to a five-field cron expression.

    Celery expands every field to a set of ints (day_of_week 0=Sunday, as in cron),
    so each set is collapsed back to its shortest form. The expression keeps Celery's
    local wall-clock time; CronRadar evaluates it in the application's time zone.

    Examples:
        crontab(hour=0, minute=0) -> '0 0 * * *'
        crontab(hour='*/6', minute=0) -> '0 */6 * * *'
        crontab(minute=0, hour=9, day_of_week='mon-fri') -> '0 9 * * 1-5'
    """
    try:
        from celery.schedules import crontab

        if not isinstance(crontab_obj, crontab):
            return None

        return ' '.join([
            _collapse_cron_field(crontab_obj.minute, 0, 59),
            _collapse_cron_field(crontab_obj.hour, 0, 23),
            _collapse_cron_field(crontab_obj.day_of_month, 1, 31),
            _collapse_cron_field(crontab_obj.month_of_year, 1, 12),
            _collapse_cron_field(crontab_obj.day_of_week, 0, 6),
        ])
    except Exception as e:
        print(f"[CronRadar.Celery] Failed to convert crontab: {e}", file=sys.stderr)
        return None


def _collapse_cron_field(values, low: int, high: int) -> str:
    """Write a set of field values as '*', '*/n', 'a-b/n', or a list of values and ranges."""
    values = sorted(values)
    if values == list(range(low, high + 1)):
        return '*'

    if len(values) >= 3:
        step = values[1] - values[0]
        if step > 1 and values == list(range(values[0], values[-1] + 1, step)):
            if values[0] == low and values[-1] + step > high:
                return f'*/{step}'
            return f'{values[0]}-{values[-1]}/{step}'

    parts = []
    run_start = previous = values[0]
    for value in values[1:] + [None]:
        if value is not None and value == previous + 1:
            previous = value
            continue
        if previous - run_start >= 2:
            parts.append(f'{run_start}-{previous}')
        else:
            parts.extend(str(v) for v in range(run_start, previous + 1))
        if value is not None:
            run_start = previous = value
    return ','.join(parts)


def schedule_to_cron(schedule) -> Optional[str]:
    """
    Convert a Celery Beat schedule to a five-field cron expression.

    Only crontab schedules have one. Intervals (timedelta, numbers, schedule(run_every=...))
    run relative to when Beat started, and solar schedules follow the sun, so both return
    None with a warning on stderr.
    """
    try:
        from celery.schedules import crontab, schedule as interval_schedule, solar

        if isinstance(schedule, crontab):
            return crontab_to_cron(schedule)

        if isinstance(schedule, solar):
            print("[CronRadar.Celery] solar schedules have no five-field cron form", file=sys.stderr)
            return None

        if isinstance(schedule, (interval_schedule, timedelta, int, float)):
            print("[CronRadar.Celery] interval schedules run relative to Beat's start and have no "
                  "five-field cron form; use crontab(...) to monitor this task", file=sys.stderr)
            return None

        print(f"[CronRadar.Celery] Unknown schedule type: {type(schedule)}", file=sys.stderr)
        return None

    except Exception as e:
        print(f"[CronRadar.Celery] Failed to convert schedule: {e}", file=sys.stderr)
        return None
