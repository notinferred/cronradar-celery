# CronRadar Celery Integration

Monitor Celery periodic tasks. Auto-discover Beat schedules and track execution. Get alerts when tasks fail or don't run on schedule.

## Installation

```bash
pip install cronradar-celery
```

## Configuration

Set environment variable:
```bash
export CRONRADAR_API_KEY=ck_app_xxxxx_yyyyy
```

Or pass it directly:

```python
setup_cronradar(app, api_key='ck_app_xxxxx_yyyyy')
```

## Quick Start

Monitor all periodic tasks by default - use `@skip_monitor` to opt-out:

```python
from celery import Celery
from cronradar_celery import setup_cronradar, skip_monitor

app = Celery('myapp')
setup_cronradar(app)

@app.task
def send_daily_report():
    # Monitored automatically
    generate_report()

@app.task
@skip_monitor
def internal_cleanup():
    # Opted out
    pass
```

## Decorator Order (Important!)

The `@skip_monitor` decorator **must** be placed **after** `@app.task`:

```python
# ✅ Correct
@app.task
@skip_monitor
def my_task():
    pass

# ❌ Wrong - won't work
@skip_monitor
@app.task
def my_task():
    pass
```

## Requirements

- Python 3.8+
- Celery 5.0+
- cronradar 1.0+

## Links

- [Documentation](https://docs.cronradar.com)
- [PyPI](https://pypi.org/project/cronradar-celery)

**See also:** [CronRadar Python SDK](https://pypi.org/project/cronradar)

## License

© 2025 [CronRadar](https://cronradar.com) - See [LICENSE](./LICENSE)
