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

Get your API key from [cronradar.com/dashboard](https://cronradar.com/dashboard)

Or pass it directly:

```python
setup_cronradar(app, mode='selective', api_key='ck_app_xxxxx_yyyyy')
```

## Quick Start - Selective Mode

Monitor specific tasks with the `@monitor` decorator:

```python
from celery import Celery
from cronradar_celery import setup_cronradar, monitor

app = Celery('myapp')
setup_cronradar(app, mode='selective')

@app.task
@monitor
def send_daily_report():
    generate_report()

@app.task
def internal_cleanup():
    # Not monitored (no decorator)
    pass
```

## Quick Start - MonitorAll Mode

Monitor all periodic tasks by default:

```python
from celery import Celery
from cronradar_celery import setup_cronradar, skip_monitor

app = Celery('myapp')
setup_cronradar(app, mode='all')

@app.task
def send_daily_report():
    # Monitored automatically
    pass

@app.task
@skip_monitor
def internal_cleanup():
    # Opted out
    pass
```

## Decorator Order (Important!)

The `@monitor` and `@skip_monitor` decorators **must** be placed **after** `@app.task`:

```python
# ✅ Correct
@app.task
@monitor
def my_task():
    pass

# ❌ Wrong - won't work
@monitor
@app.task
def my_task():
    pass
```

## Requirements

- Python 3.8+
- Celery 5.0+
- cronradar 1.0+

## Links

- 📚 [Documentation](https://cronradar.com/docs/sdks/celery)
- 📦 [PyPI](https://pypi.org/project/cronradar-celery)
- 🐛 [GitHub Issues](https://github.com/cronradar/cronradar-celery/issues)
- ✉️ support@cronradar.com

## License

Proprietary - © 2025 CronRadar. All rights reserved.

See [LICENSE](./LICENSE) for details. This integration may only be used with the CronRadar monitoring service.
