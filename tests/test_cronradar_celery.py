"""
CronRadar Celery SDK Tests
"""

import os
import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock

from cronradar_celery import setup_cronradar, skip_monitor
from cronradar_celery.utils import (
    normalize_task_name,
    generate_readable_name,
    timedelta_to_cron,
)
from cronradar_celery.monitors import should_monitor_task, skip_monitor_decorator


class TestNormalizeTaskName:
    """Tests for normalize_task_name()."""

    def test_converts_dots_to_hyphens(self):
        """Should convert dots to hyphens."""
        result = normalize_task_name('myapp.tasks.send_email')
        assert '.' not in result
        assert 'myapp-tasks-send-email' == result

    def test_converts_underscores_to_hyphens(self):
        """Should convert underscores to hyphens."""
        result = normalize_task_name('process_queue')
        assert '_' not in result
        assert 'process-queue' == result

    def test_lowercases_name(self):
        """Should lowercase the name."""
        result = normalize_task_name('MyApp.Tasks.SendEmail')
        assert result == result.lower()

    def test_handles_empty_string(self):
        """Should handle empty string."""
        result = normalize_task_name('')
        assert result == ''

    def test_handles_none(self):
        """Should handle None."""
        result = normalize_task_name(None)
        assert result is None

    def test_limits_length(self):
        """Should limit length to MAX_MONITOR_KEY_LENGTH (200)."""
        from cronradar.constants import MAX_MONITOR_KEY_LENGTH
        long_name = 'a' * (MAX_MONITOR_KEY_LENGTH + 50)
        result = normalize_task_name(long_name)
        assert len(result) <= MAX_MONITOR_KEY_LENGTH

    def test_removes_special_characters(self):
        """Should remove special characters except hyphens."""
        result = normalize_task_name('task@name!with#special')
        assert '@' not in result
        assert '!' not in result
        assert '#' not in result


class TestGenerateReadableName:
    """Tests for generate_readable_name()."""

    def test_extracts_last_part(self):
        """Should extract the last part after final dot."""
        result = generate_readable_name('myapp.tasks.send_email')
        assert 'Send Email' == result

    def test_converts_snake_case(self):
        """Should convert snake_case to Title Case."""
        result = generate_readable_name('send_email')
        assert 'Send Email' == result

    def test_handles_empty_string(self):
        """Should handle empty string."""
        result = generate_readable_name('')
        assert result == ''

    def test_handles_none(self):
        """Should handle None."""
        result = generate_readable_name(None)
        assert result is None

    def test_capitalizes_simple_name(self):
        """Should capitalize simple name."""
        result = generate_readable_name('backup')
        assert result == 'Backup'


class TestTimedeltaToCron:
    """Tests for timedelta_to_cron()."""

    def test_every_minute(self):
        """Should return every minute cron for 60 seconds."""
        result = timedelta_to_cron(timedelta(seconds=60))
        assert result == '* * * * *'

    def test_every_5_minutes(self):
        """Should return every 5 minutes cron."""
        result = timedelta_to_cron(timedelta(minutes=5))
        assert result == '*/5 * * * *'

    def test_every_15_minutes(self):
        """Should return every 15 minutes cron."""
        result = timedelta_to_cron(timedelta(minutes=15))
        assert result == '*/15 * * * *'

    def test_every_30_minutes(self):
        """Should return every 30 minutes cron."""
        result = timedelta_to_cron(timedelta(minutes=30))
        assert result == '*/30 * * * *'

    def test_every_hour(self):
        """Should return hourly cron."""
        result = timedelta_to_cron(timedelta(hours=1))
        assert result == '0 * * * *'

    def test_every_2_hours(self):
        """Should return every 2 hours cron."""
        result = timedelta_to_cron(timedelta(hours=2))
        assert result == '0 */2 * * *'

    def test_daily(self):
        """Should return daily cron."""
        result = timedelta_to_cron(timedelta(days=1))
        assert result == '0 0 * * *'

    def test_weekly(self):
        """Should return weekly cron."""
        result = timedelta_to_cron(timedelta(weeks=1))
        assert result == '0 0 * * 0'

    def test_sub_minute(self):
        """Should return every minute for sub-minute intervals."""
        result = timedelta_to_cron(timedelta(seconds=30))
        assert result == '* * * * *'


class TestSkipMonitorDecorator:
    """Tests for skip_monitor decorator."""

    def test_sets_skip_attribute(self):
        """Should set _cronradar_skip attribute."""
        @skip_monitor_decorator
        def my_task():
            pass

        assert hasattr(my_task, '_cronradar_skip')
        assert my_task._cronradar_skip is True

    def test_preserves_function(self):
        """Should preserve original function."""
        def original_func():
            return 'result'

        decorated = skip_monitor_decorator(original_func)

        assert decorated() == 'result'


class TestShouldMonitorTask:
    """Tests for should_monitor_task()."""

    def test_returns_true_by_default(self):
        """Should return True for regular tasks."""
        mock_task = MagicMock()
        mock_task.run = lambda: None

        result = should_monitor_task(mock_task)

        assert result is True

    def test_returns_false_for_skipped_task(self):
        """Should return False for tasks with skip decorator."""
        @skip_monitor_decorator
        def skipped_task():
            pass

        mock_task = MagicMock()
        mock_task.run = skipped_task

        result = should_monitor_task(mock_task)

        assert result is False

    def test_returns_true_if_no_run_method(self):
        """Should return True if task has no run method."""
        mock_task = MagicMock(spec=[])

        result = should_monitor_task(mock_task)

        assert result is True


class TestSetupCronradar:
    """Tests for setup_cronradar()."""

    def setup_method(self):
        """Reset initialization state before each test."""
        import cronradar_celery
        cronradar_celery._initialized = False

    def teardown_method(self):
        """Clean up after each test."""
        import cronradar_celery
        cronradar_celery._initialized = False
        if 'CRONRADAR_API_KEY' in os.environ:
            del os.environ['CRONRADAR_API_KEY']

    @patch('cronradar_celery.discover_and_sync_tasks')
    @patch('cronradar_celery.setup_task_monitoring')
    def test_initializes_monitoring(self, mock_setup, mock_discover):
        """Should initialize task monitoring."""
        mock_app = MagicMock()

        setup_cronradar(mock_app)

        mock_setup.assert_called_once_with(mock_app)
        mock_discover.assert_called_once_with(mock_app)

    @patch('cronradar_celery.discover_and_sync_tasks')
    @patch('cronradar_celery.setup_task_monitoring')
    def test_sets_api_key_if_provided(self, mock_setup, mock_discover):
        """Should set API key in environment if provided."""
        mock_app = MagicMock()

        setup_cronradar(mock_app, api_key='custom-api-key')

        assert os.environ.get('CRONRADAR_API_KEY') == 'custom-api-key'

    @patch('cronradar_celery.discover_and_sync_tasks')
    @patch('cronradar_celery.setup_task_monitoring')
    def test_ignores_duplicate_calls(self, mock_setup, mock_discover):
        """Should ignore duplicate setup calls."""
        mock_app = MagicMock()

        setup_cronradar(mock_app)
        setup_cronradar(mock_app)

        assert mock_setup.call_count == 1
        assert mock_discover.call_count == 1


class TestSkipMonitorIntegration:
    """Integration tests for skip_monitor functionality."""

    def test_skip_monitor_with_celery_task(self):
        """Should work as Celery task decorator."""
        # Simulate Celery task decorator pattern
        @skip_monitor
        def my_monitored_task():
            return 'result'

        assert hasattr(my_monitored_task, '_cronradar_skip')
        assert my_monitored_task._cronradar_skip is True
        assert my_monitored_task() == 'result'
