"""
Utility functions for Celery integration.
"""

import sys
import re
from typing import Optional
from datetime import timedelta


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

    # Limit length
    if len(key) > 64:
        key = key[:64]

    return key


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
    Convert Celery crontab schedule to cron expression string.

    Args:
        crontab_obj: celery.schedules.crontab instance

    Returns:
        Cron expression string or None if conversion fails

    Examples:
        crontab(hour=0, minute=0) -> '0 0 * * *'
        crontab(hour='*/6', minute=0) -> '0 */6 * * *'
    """
    try:
        from celery.schedules import crontab

        if not isinstance(crontab_obj, crontab):
            return None

        # Extract fields (minute, hour, day_of_month, month, day_of_week)
        minute = _format_cron_field(crontab_obj.minute)
        hour = _format_cron_field(crontab_obj.hour)
        day_of_month = _format_cron_field(crontab_obj.day_of_month)
        month = _format_cron_field(crontab_obj.month_of_year)
        day_of_week = _format_cron_field(crontab_obj.day_of_week)

        return f"{minute} {hour} {day_of_month} {month} {day_of_week}"
    except Exception as e:
        print(f"[CronRadar.Celery] Failed to convert crontab: {e}", file=sys.stderr)
        return None


def timedelta_to_cron(interval: timedelta) -> str:
    """
    Convert timedelta interval to approximate cron expression.

    Args:
        interval: timedelta representing the repeat interval

    Returns:
        Approximate cron expression

    Examples:
        timedelta(hours=1) -> '0 * * * *'
        timedelta(days=1) -> '0 0 * * *'
    """
    total_seconds = interval.total_seconds()

    # Convert to common intervals
    if total_seconds < 60:
        return "* * * * *"  # Every minute (can't represent sub-minute)
    elif total_seconds == 60:
        return "* * * * *"  # Every minute
    elif total_seconds == 300:
        return "*/5 * * * *"  # Every 5 minutes
    elif total_seconds == 900:
        return "*/15 * * * *"  # Every 15 minutes
    elif total_seconds == 1800:
        return "*/30 * * * *"  # Every 30 minutes
    elif total_seconds == 3600:
        return "0 * * * *"  # Every hour
    elif total_seconds % 3600 == 0 and total_seconds < 86400:
        hours = int(total_seconds / 3600)
        return f"0 */{hours} * * *"  # Every N hours
    elif total_seconds == 86400:
        return "0 0 * * *"  # Daily
    elif total_seconds == 604800:
        return "0 0 * * 0"  # Weekly (Sunday)
    else:
        # Default to hourly for other intervals
        return "0 * * * *"


def _format_cron_field(field) -> str:
    """
    Format a Celery crontab field for cron expression.

    Celery uses sets for multiple values and '*' for all.
    """
    if field is None or field == '*':
        return '*'

    # If it's a set, join with commas
    if isinstance(field, set):
        return ','.join(str(x) for x in sorted(field))

    # If it's a string, return as-is (handles '*/N' patterns)
    if isinstance(field, str):
        return field

    # Single value
    return str(field)


def schedule_to_cron(schedule) -> Optional[str]:
    """
    Convert any Celery schedule object to cron expression.

    Args:
        schedule: Celery schedule object (crontab, timedelta, solar, etc.)

    Returns:
        Cron expression string or None if conversion fails
    """
    try:
        from celery.schedules import crontab, schedule as base_schedule

        # Handle crontab directly
        if isinstance(schedule, crontab):
            return crontab_to_cron(schedule)

        # Handle schedule objects with run_every (timedelta-based)
        if isinstance(schedule, base_schedule) and hasattr(schedule, 'run_every'):
            if isinstance(schedule.run_every, timedelta):
                return timedelta_to_cron(schedule.run_every)

        # Handle raw timedelta
        if isinstance(schedule, timedelta):
            return timedelta_to_cron(schedule)

        # Unknown schedule type
        print(f"[CronRadar.Celery] Unknown schedule type: {type(schedule)}", file=sys.stderr)
        return None

    except Exception as e:
        print(f"[CronRadar.Celery] Failed to convert schedule: {e}", file=sys.stderr)
        return None
