# CronRadar for Celery

Auto-discovery for Celery periodic tasks. Add `setup_cronradar(app)` to your Celery app — every task with a Beat schedule is registered with CronRadar, watched for missed runs, and alerted on if it fails.

Built on top of the [`cronradar`](https://pypi.org/project/cronradar) base SDK.

## Install

```bash
pip install cronradar-celery
# or
poetry add cronradar-celery
# or
uv add cronradar-celery
```

Python 3.8+ supported. Celery 5.0+.

## Setup

The SDK reads its API key from the `CRONRADAR_API_KEY` environment variable.

```bash
export CRONRADAR_API_KEY=ck_app_xxxxxxxxxxxxxxxxxxxx
```

Or pass it explicitly to `setup_cronradar(...)`:

```python
setup_cronradar(app, api_key='ck_app_xxxxxxxxxxxxxxxxxxxx')
```

Get the API key from the CronRadar dashboard at [app.cronradar.com](https://app.cronradar.com) under your application's settings. API keys have the form `ck_app_<random>`.

The Celery integration runs once on worker / beat startup and listens to every task execution — no per-task initialization is needed.

## Quickstart

Call `setup_cronradar(app)` once on your Celery app:

```python
from celery import Celery
from cronradar_celery import setup_cronradar, skip_monitor

app = Celery('myapp', broker='redis://localhost:6379/0')

# Configure your Beat schedule as usual
app.conf.beat_schedule = {
    'send-daily-report': {
        'task': 'tasks.send_daily_report',
        'schedule': '0 8 * * *',  # 8am daily
    },
}

# Hook CronRadar in
setup_cronradar(app)

@app.task
def send_daily_report():
    generate_report()
```

That's it. On worker / Beat startup, the integration:

- Walks every entry in `app.conf.beat_schedule`
- Pre-syncs each scheduled task to CronRadar (so they appear in the dashboard immediately)
- Translates `crontab(...)`, `schedule(timedelta(...))`, and string schedules into standard 5-field POSIX cron
- Connects to Celery's `task_prerun`, `task_success`, and `task_failure` signals to record `start` / `complete` / `fail` per execution

## Decorators

### Opt out per task

Decorate a Celery task with `@skip_monitor` to exclude it from auto-monitoring.

> **Order matters:** `@app.task` must come *first* (outermost), `@skip_monitor` second. Celery resolves the outer decorator at registration time; reversing the order breaks task discovery.

```python
from cronradar_celery import skip_monitor

@app.task
@skip_monitor
def internal_cleanup():
    # not monitored — internal/maintenance tasks you don't need alerts for
    pass
```

### Custom monitor keys

Monitor keys default to the Celery task name (lowercased, dots → dashes). Override the task name itself if you need a different key:

```python
@app.task(name='critical-payment-processor')
def process_payments():
    # registered in CronRadar as "critical-payment-processor"
    pass
```

The integration uses `task.name` as the monitor key.

## Reference

### `setup_cronradar(app, api_key=None)`

Wires the integration to a Celery app. Called once at application startup.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `app` | `celery.Celery` | yes | The Celery app instance. |
| `api_key` | `str` | optional | API key. Falls back to `CRONRADAR_API_KEY` env var if omitted. |

What it does:

1. Reads `app.conf.beat_schedule` and pre-syncs each entry to CronRadar.
2. Connects signal handlers (`task_prerun`, `task_success`, `task_failure`) for lifecycle tracking.

Idempotent — safe to call multiple times if you have multiple Celery apps.

Grace period is configured per-monitor on CronRadar (default 60 seconds; set via the dashboard).

### Decorators

| Decorator | Purpose |
|---|---|
| `@skip_monitor` | Exclude this task from monitoring even if it has a Beat schedule. |

`@skip_monitor` must be placed **after** `@app.task`:

```python
@app.task
@skip_monitor
def internal_cleanup():
    return 'done'
```

### Schedule translation

The integration accepts these schedule types in `beat_schedule`:

| Beat schedule | Translated to CronRadar |
|---|---|
| `'0 8 * * *'` (string) | `0 8 * * *` (passthrough) |
| `crontab(hour=8, minute=0)` | `0 8 * * *` |
| `crontab(hour=8, minute=0, day_of_week='mon-fri')` | `0 8 * * 1-5` |
| `schedule(run_every=timedelta(hours=1))` | `0 * * * *` |

If a schedule isn't translatable to standard cron (e.g., `solar(...)` schedules, sub-minute intervals), the integration logs a warning and that task is not monitored. Other tasks continue normally.

## Configuration

| Environment variable | Required | Default | Purpose |
|---|---|---|---|
| `CRONRADAR_API_KEY` | yes | — | API key from the CronRadar dashboard. Format `ck_app_xxxxx`. |
| `CRONRADAR_BASE_URL` | no | `https://cron.life` | Override the ingestion endpoint. |
| `CRONRADAR_TIMEOUT` | no | `5.0` | HTTP request timeout in seconds. |
| `CRONRADAR_LOG_ERRORS` | no | `1` | Set to `0` to suppress stderr warnings on network failure. |

## Error handling

The integration upholds the same hard guarantees as the base SDK:

1. **Never raises to user code.** Network errors, timeouts, 4xx/5xx responses — all caught and logged. A failing CronRadar API must not break a Celery task.
2. **Never alters task execution.** The integration uses Celery signals; it never modifies task state, results, or retry behavior. If your task raises, Celery's normal retry/error policy runs unchanged.

What this looks like at runtime:

| Situation | SDK behavior | Celery behavior |
|---|---|---|
| CronRadar API unreachable | Logs once; returns | Task runs and is marked SUCCESS/FAILURE normally |
| Sync on startup fails for one task | Logs; continues | Other tasks sync; worker starts |
| Per-task ping fails | Logs; returns | Task state unchanged |
| User task raises | Records `fail_job` with exception message | Celery applies retry/error policy |
| Beat schedule not translatable | Warns; that task is not monitored | Beat still triggers it normally |

## Troubleshooting

### Tasks aren't showing up in the CronRadar dashboard

1. **Confirm `setup_cronradar(app)` is called once** — typically right after `app = Celery(...)` and after `app.conf.beat_schedule = {...}` is set.
2. **Confirm tasks are in `app.conf.beat_schedule`.** Tasks invoked via `task.delay(...)` are not periodic and are not auto-monitored. Use the base [`cronradar`](https://pypi.org/project/cronradar) SDK to instrument those manually.
3. **Check `CRONRADAR_API_KEY`** — see "401 Unauthorized" in stderr if it's missing or wrong.
4. **Verify Beat is actually running.** Without Beat, no schedule fires, and CronRadar will eventually alert "monitor never executed."

### `@skip_monitor` doesn't seem to apply

Decorator order. The outer decorator must be `@app.task`:

```python
# correct
@app.task
@skip_monitor
def my_task():
    return 'done'

# wrong — Celery never registers this as a task
@skip_monitor
@app.task
def my_task():
    return 'done'
```

### Some tasks log "schedule not translatable"

You're using a `solar(...)` schedule, a sub-minute interval, or a custom Beat schedule class. CronRadar monitors at minute resolution; these can't be expressed in standard cron. Either coarsen the schedule, or wrap the task body manually with the base SDK.

### My task is `@app.task(name='my.dotted.name')` — what's the monitor key?

The monitor key matches Celery's task name, normalized to lowercase with dots replaced by dashes: `my.dotted.name` becomes `my-dotted-name`. Override with `@monitor(key='explicit-key')` to make it whatever you want.

### How do I migrate from `setup_cronradar(app, mode='all')`?

Earlier versions accepted a `mode` argument with values like `'all'` and `'opt-in'`. The current model is `MonitorAll` (always) plus `@skip_monitor` to opt out. Migration:

1. Drop the `mode` argument from `setup_cronradar()` calls.
2. Add `@skip_monitor` to any task that was previously *not* covered under `mode='opt-in'`.

The `mode` argument is removed in this version; passing it raises `TypeError`, which is intentional — agents reading old snippets get a clear signal to update.

## Links

- **Documentation:** [docs.cronradar.com](https://docs.cronradar.com)
- **Agent-friendly index:** [docs.cronradar.com/llms.txt](https://docs.cronradar.com/llms.txt)
- **OpenAPI spec:** [api.cronradar.com/swagger/v1/swagger.json](https://api.cronradar.com/swagger/v1/swagger.json)
- **PyPI:** [pypi.org/project/cronradar-celery](https://pypi.org/project/cronradar-celery)
- **GitHub:** [github.com/cronradar/cronradar-celery](https://github.com/cronradar/cronradar-celery)
- **Base SDK:** [pypi.org/project/cronradar](https://pypi.org/project/cronradar)
- **Support:** support@cronradar.com

## License

© 2026 [CronRadar](https://cronradar.com) · Proprietary — see [LICENSE](./LICENSE).
