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
    schedule_to_cron,
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

    def test_matches_the_shared_shortening_vector(self):
        """Keys over 100 characters shorten exactly as docs/SDK_SPECIFICATION.md "Monitor Keys" specifies."""
        result = normalize_task_name('abcdef-' * 15 + 'end')
        assert result == 'abcdef-' * 12 + 'abcdef-4f91bd6e'
        assert len(result) == 99

    def test_shortens_to_91_characters_and_a_hash(self):
        """A key over the limit keeps its first 91 characters and a hash suffix."""
        result = normalize_task_name('nightly.' + 'x' * 95)
        assert result == 'nightly-' + 'x' * 83 + '-89d49067'
        assert len(result) == 100

    def test_keeps_a_key_at_the_limit(self):
        """A 100-character key is unchanged."""
        assert normalize_task_name('k' * 100) == 'k' * 100

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


def next_cron_run(expression, after):
    """The first minute after `after` matching a numeric five-field expression,
    with both day fields required to match, as CronRadar evaluates them."""
    bounds = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
    minutes, hours, days, months, weekdays = (
        expand_cron_field(field, low, high)
        for field, (low, high) in zip(expression.split(' '), bounds))
    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    while True:
        if candidate.month not in months:
            candidate = (candidate.replace(day=1, hour=0, minute=0) + timedelta(days=32)).replace(day=1)
        elif candidate.day not in days or candidate.isoweekday() % 7 not in weekdays:
            candidate = candidate.replace(hour=0, minute=0) + timedelta(days=1)
        elif candidate.hour not in hours:
            candidate = candidate.replace(minute=0) + timedelta(hours=1)
        elif candidate.minute not in minutes:
            candidate += timedelta(minutes=1)
        else:
            return candidate


def expand_cron_field(field, low, high):
    values = set()
    for part in field.split(','):
        span, _, step = part.partition('/')
        if span == '*':
            first, last = low, high
        elif '-' in span:
            first, last = (int(bound) for bound in span.split('-'))
        else:
            first = last = int(span)
        if step and span != '*' and '-' not in span:
            last = high
        values.update(range(first, last + 1, int(step or 1)))
    return values


def next_celery_runs(schedule, start, count):
    """Run times Celery Beat computes for `schedule`, each from the previous run."""
    runs, last_run = [], start
    for _ in range(count):
        schedule.nowfun = lambda moment=last_run: moment
        last_run = last_run + schedule.remaining_estimate(last_run)
        runs.append(last_run)
    return runs


@pytest.fixture
def utc_app():
    from celery import Celery
    app = Celery('translation', broker='memory://', backend='cache+memory://')
    app.conf.timezone = 'UTC'
    yield app
    app.close()


CRONTAB_TRANSLATIONS = [
    (dict(), '* * * * *'),
    (dict(minute=0, hour=0), '0 0 * * *'),
    (dict(minute='*/15'), '*/15 * * * *'),
    (dict(minute='5-55/10'), '5-55/10 * * * *'),
    (dict(minute='0,30', hour='*/6'), '0,30 */6 * * *'),
    (dict(minute=0, hour='9-17'), '0 9-17 * * *'),
    (dict(minute=0, hour='0-6,22,23'), '0 0-6,22,23 * * *'),
    (dict(minute=0, hour=9, day_of_week='mon-fri'), '0 9 * * 1-5'),
    (dict(minute=0, hour=9, day_of_week='sun'), '0 9 * * 0'),
    (dict(minute=0, hour=9, day_of_week='sat,sun'), '0 9 * * 0,6'),
    (dict(minute=0, hour=9, day_of_week='*/2'), '0 9 * * */2'),
    (dict(minute=0, hour=9, day_of_week=0), '0 9 * * 0'),
    (dict(minute=0, hour=3, day_of_month='1,15'), '0 3 1,15 * *'),
    (dict(minute=0, hour=3, day_of_month='1-7', day_of_week='mon'), '0 3 1-7 * 1'),
    (dict(minute=0, hour=3, day_of_month=1, month_of_year='*/3'), '0 3 1 */3 *'),
    (dict(minute=0, hour=3, day_of_month=1, month_of_year='2-12/2'), '0 3 1 2-12/2 *'),
    (dict(minute={0, 30}, hour={1, 2, 3, 7}), '0,30 1-3,7 * * *'),
    (dict(minute=[0, 15], hour=range(8, 12)), '0,15 8-11 * * *'),
]


class TestCrontabTranslation:
    """crontab(...) translations against Celery's own run times."""

    @pytest.mark.parametrize('fields,expected', CRONTAB_TRANSLATIONS)
    def test_translation_is_compact_five_field_cron(self, fields, expected, utc_app):
        from celery.schedules import crontab
        assert schedule_to_cron(crontab(app=utc_app, **fields)) == expected

    @pytest.mark.parametrize('fields,expected', CRONTAB_TRANSLATIONS)
    def test_translation_runs_when_celery_runs(self, fields, expected, utc_app):
        from celery.schedules import crontab
        from datetime import datetime, timezone
        schedule = crontab(app=utc_app, **fields)
        expression = schedule_to_cron(crontab(app=utc_app, **fields))
        start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        celery_runs = next_celery_runs(schedule, start, 12)
        cron_runs, previous = [], start
        for _ in celery_runs:
            previous = next_cron_run(expression, previous)
            cron_runs.append(previous)
        assert cron_runs == celery_runs

    def test_every_translation_fits_the_server_schedule_limit(self, utc_app):
        from celery.schedules import crontab
        odd_minutes = crontab(app=utc_app, minute=','.join(str(m) for m in range(1, 60, 2)))
        scattered = crontab(app=utc_app, minute='1,4,9,16,25,36,49', hour='1,3,7,9,13,19,23')
        assert schedule_to_cron(odd_minutes) == '1-59/2 * * * *'
        assert len(schedule_to_cron(scattered)) <= 100

    def test_expression_is_not_shifted_for_the_app_time_zone(self):
        from celery import Celery
        from celery.schedules import crontab
        app = Celery('new-york', broker='memory://')
        app.conf.timezone = 'America/New_York'
        assert schedule_to_cron(crontab(minute=0, hour=9, app=app)) == '0 9 * * *'
        app.close()


class TestUntranslatableSchedules:
    """Schedules without a five-field form are skipped with a warning."""

    @pytest.mark.parametrize('beat_schedule', [
        timedelta(hours=1),
        timedelta(seconds=30),
        900.0,
    ])
    def test_intervals_are_skipped(self, beat_schedule, capsys):
        from celery.schedules import schedule
        assert schedule_to_cron(beat_schedule) is None
        assert schedule_to_cron(schedule(run_every=timedelta(hours=1))) is None
        assert 'interval' in capsys.readouterr().err

    def test_solar_is_skipped(self, capsys):
        from celery.schedules import solar
        sunrise = object.__new__(solar)
        assert schedule_to_cron(sunrise) is None
        assert 'solar' in capsys.readouterr().err


class TestDiscoveryTimeZone:
    """Discovery sends Celery's local expression and points at the application's zone."""

    def discover(self, app):
        from cronradar_celery.discovery import discover_and_sync_tasks
        with patch('cronradar.sync_monitors') as sync:
            discover_and_sync_tasks(app)
        return sync.call_args[0][0]

    def beat_app(self, timezone_name, **crontab_options):
        from celery import Celery
        from celery.schedules import crontab
        app = Celery('zones', broker='memory://')
        app.conf.timezone = timezone_name
        app.conf.beat_schedule = {
            'report': {'task': 'tasks.report', 'schedule': crontab(minute=0, hour=9, **crontab_options)},
            'poll': {'task': 'tasks.poll', 'schedule': timedelta(minutes=5)},
        }
        return app

    def test_non_utc_app_warns_once_and_sends_local_expression(self, capsys):
        app = self.beat_app('America/New_York')
        monitors = self.discover(app)
        self.discover(app)
        err = capsys.readouterr().err
        assert monitors == [{'key': 'tasks-report', 'schedule': '0 9 * * *', 'name': 'Report'}]
        assert err.count('crontab schedules in America/New_York') == 1
        assert "Skipping 'tasks.poll'" in err
        app.close()

    @pytest.mark.parametrize('zone', ['UTC', 'Etc/UTC', None])
    def test_utc_app_does_not_warn(self, zone, capsys):
        app = self.beat_app(zone)
        self.discover(app)
        assert 'time zone' not in capsys.readouterr().err
        app.close()

    def test_custom_nowfun_warns(self, capsys):
        from datetime import datetime, timezone
        app = self.beat_app('UTC', nowfun=lambda: datetime.now(timezone.utc))
        monitors = self.discover(app)
        assert monitors[0]['schedule'] == '0 9 * * *'
        assert 'nowfun' in capsys.readouterr().err
        app.close()


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
