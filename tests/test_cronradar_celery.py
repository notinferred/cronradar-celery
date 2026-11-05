"""
CronRadar Celery SDK Tests
"""

import os
import gc
import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock

from cronradar_celery import setup_cronradar, skip_monitor
from cronradar_celery.utils import (
    normalize_task_name,
    generate_readable_name,
    timedelta_to_cron,
)
from cronradar_celery.monitors import should_monitor_task, skip_monitor_decorator, setup_task_monitoring


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
        self.original_api_key = os.environ.get('CRONRADAR_API_KEY')

    def teardown_method(self):
        """Clean up after each test."""
        if self.original_api_key is None:
            os.environ.pop('CRONRADAR_API_KEY', None)
        else:
            os.environ['CRONRADAR_API_KEY'] = self.original_api_key

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

    @patch('cronradar_celery.discover_and_sync_tasks')
    @patch('cronradar_celery.setup_task_monitoring')
    def test_initializes_each_app_once(self, mock_setup, mock_discover):
        first, second = MagicMock(), MagicMock()
        setup_cronradar(first)
        setup_cronradar(second)
        setup_cronradar(first)
        assert mock_setup.call_count == mock_discover.call_count == 2
        assert first._cronradar_initialized is True
        assert second._cronradar_initialized is True

    @patch('cronradar_celery.discover_and_sync_tasks')
    @patch('cronradar_celery.setup_task_monitoring')
    def test_failed_setup_does_not_break_startup_and_can_be_retried(self, mock_setup, mock_discover):
        app = MagicMock()
        mock_setup.side_effect = RuntimeError('Monitoring unavailable')
        setup_cronradar(app)
        assert getattr(app, '_cronradar_initialized', False) is not True
        mock_setup.side_effect = None
        setup_cronradar(app)
        assert app._cronradar_initialized is True
        assert mock_setup.call_count == 2
        assert mock_discover.call_count == 1


@pytest.fixture
def celery_apps():
    from celery import Celery
    apps = []

    def create(name):
        app = Celery(name, broker='memory://', backend='cache+memory://')
        app.conf.task_ignore_result = True
        apps.append(app)
        return app

    yield create

    for app in apps:
        for signal, receiver in getattr(app, '_cronradar_signal_receivers', ()):
            signal.disconnect(receiver)
        app.close()


def local_task(app, name, function=None):
    def work():
        return 'job-result'
    return app.task(name=name, shared=False, lazy=False)(function or work)


@patch('cronradar.fail_job')
@patch('cronradar.complete_job')
@patch('cronradar.start_job')
def test_real_signals_survive_collection_and_repeated_setup(start, complete, fail, celery_apps):
    from celery.signals import task_prerun, task_success, task_failure
    app = celery_apps('signal-lifetime')
    task = local_task(app, 'proof.periodic')
    setup_task_monitoring(app)
    first_receivers = app._cronradar_signal_receivers
    setup_task_monitoring(app)
    assert app._cronradar_signal_receivers is first_receivers
    gc.collect()

    task_prerun.send(sender=task, task=task, task_id='local-proof')
    task_success.send(sender=task, result='job-result')
    task_failure.send(sender=task, task_id='local-proof', exception=ValueError('Sample failure'))

    start.assert_called_once_with('proof-periodic')
    complete.assert_called_once_with('proof-periodic')
    fail.assert_called_once_with('proof-periodic', 'Sample failure')


@patch('cronradar.start_job')
def test_multiple_apps_report_once_and_ignore_unconfigured_apps(start, celery_apps):
    from celery.signals import task_prerun
    first, second, other = [celery_apps(name) for name in ('first', 'second', 'other')]
    setup_task_monitoring(first)
    setup_task_monitoring(second)
    gc.collect()
    for app, name in ((first, 'proof.first'), (second, 'proof.second'), (other, 'proof.other')):
        task = local_task(app, name)
        task_prerun.send(sender=task, task=task, task_id='local-proof')
    assert [call.args for call in start.call_args_list] == [('proof-first',), ('proof-second',)]


@patch('cronradar.start_job')
def test_internal_reconcile_and_opted_out_jobs_do_not_report(start, celery_apps):
    from celery.signals import task_prerun
    from cronradar_celery import RECONCILE_TASK_NAME
    app = celery_apps('skipped-tasks')
    setup_task_monitoring(app)

    @skip_monitor
    def skipped():
        return 'unchanged'

    for task in (local_task(app, RECONCILE_TASK_NAME), local_task(app, 'proof.skip', skipped)):
        task_prerun.send(sender=task, task=task, task_id='local-proof')
    start.assert_not_called()


@patch('cronradar_celery.discover_and_sync_tasks')
def test_each_apps_reconcile_task_uses_its_own_schedule(discover, celery_apps):
    from cronradar_celery import RECONCILE_TASK_NAME
    first, second = celery_apps('first-registry'), celery_apps('second-registry')
    setup_cronradar(first)
    setup_cronradar(second)
    discover.reset_mock()
    first.tasks[RECONCILE_TASK_NAME].run()
    second.tasks[RECONCILE_TASK_NAME].run()
    assert [call.args[0] for call in discover.call_args_list] == [first, second]


@patch('cronradar.complete_job', side_effect=RuntimeError('Monitoring unavailable'))
@patch('cronradar.start_job', side_effect=RuntimeError('Monitoring unavailable'))
def test_monitoring_signal_errors_preserve_actual_task_result(start, complete, celery_apps):
    app = celery_apps('fail-open-worker')
    setup_task_monitoring(app)
    task = local_task(app, 'proof.success')
    result = task.apply(throw=True)
    assert result.result == 'job-result'
    start.assert_called_once()
    complete.assert_called_once()


@patch('cronradar.fail_job', side_effect=RuntimeError('Monitoring unavailable'))
@patch('cronradar.start_job')
def test_monitoring_signal_errors_preserve_actual_task_failure(start, fail, celery_apps):
    app = celery_apps('failed-worker')
    setup_task_monitoring(app)
    original = ValueError('Original job failure')

    def work():
        raise original

    task = local_task(app, 'proof.failure', work)
    result = task.apply(throw=False)
    assert result.result is original
    with pytest.raises(ValueError) as raised:
        result.get(propagate=True)
    assert raised.value is original
    fail.assert_called_once_with('proof-failure', 'Original job failure')


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
