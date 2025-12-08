# CronRadar Celery Integration

Monitor Celery periodic tasks. Auto-discover Beat schedules and track execution. Get alerts when tasks fail or don't run on schedule.

## Installation

```bash
pip install cronradar-celery
```

## Quick Start

### Selective Mode

Monitor specific tasks with the `@monitor` decorator:

```python
from celery import Celery
from cronradar_celery import setup_cronradar, monitor

app = Celery('myapp')

# Enable selective monitoring
setup_cronradar(app, mode='selective')

# Only monitored tasks
@app.task
@monitor
def send_daily_report():
    # Your task logic
    pass

# Not monitored
@app.task
def internal_cleanup():
    # This task won't be monitored
    pass
```

### MonitorAll Mode

Monitor all periodic tasks automatically:

```python
from celery import Celery
from cronradar_celery import setup_cronradar, skip_monitor

app = Celery('myapp')

# Enable comprehensive monitoring
setup_cronradar(app, mode='all')

# All tasks monitored by default
@app.task
def send_daily_report():
    pass

# Opt-out specific tasks
@app.task
@skip_monitor
def internal_cleanup():
    # This task won't be monitored
    pass
```

## Features

- **Auto-Discovery**: Automatically finds and syncs Celery Beat periodic tasks
- **Zero Configuration**: Add one line to your Celery setup
- **Schedule Detection**: Extracts cron expressions from Beat schedules (crontab and timedelta)
- **No Task Changes**: Monitor tasks without modifying task logic
- **Selective or Comprehensive**: Choose opt-in or opt-out monitoring

## Configuration

Set your API key via environment variable:

```bash
export CRONRADAR_API_KEY=ck_app_xxxxx_yyyyy
```

Get your API key from [cronradar.com](https://cronradar.com)

### Advanced Configuration

```python
from cronradar_celery import setup_cronradar

# Pass API key directly (optional)
setup_cronradar(app, mode='selective', api_key='ck_app_xxxxx_yyyyy')

# Choose monitoring mode
setup_cronradar(app, mode='selective')  # Opt-in with @monitor
setup_cronradar(app, mode='all')        # Opt-out with @skip_monitor
```

## How It Works

1. **Setup**: Call `setup_cronradar(app)` after creating your Celery app
2. **Auto-Discovery**: Integration inspects `app.conf.beat_schedule` and syncs all periodic tasks
3. **Task Execution**: When tasks complete successfully, execution is recorded via Celery signals
4. **Monitoring**: CronRadar tracks execution and alerts if tasks don't run on schedule

## Beat Schedule Support

Works with both crontab and timedelta schedules:

```python
from celery.schedules import crontab
from datetime import timedelta

app.conf.beat_schedule = {
    'send-report-daily': {
        'task': 'tasks.send_report',
        'schedule': crontab(hour=0, minute=0),  # ✓ Converts to '0 0 * * *'
    },
    'cleanup-hourly': {
        'task': 'tasks.cleanup',
        'schedule': timedelta(hours=1),  # ✓ Converts to '0 * * * *'
    },
}
```

## Requirements

- Python 3.8+
- Celery 5.0+
- cronradar 1.0+

## Links

📚 [Documentation](https://cronradar.com/docs)
🐛 [Issues](https://github.com/cronradar/cronradar-celery/issues)
✉️ support@cronradar.com

## License

Proprietary - © 2025 CronRadar. All rights reserved.

See [LICENSE](./LICENSE) for details. This integration may only be used with the CronRadar monitoring service.
