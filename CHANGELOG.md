# Changelog

All notable changes to `cronradar-celery` are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [0.1.3] - 2026-11-17

### Fixed
- `crontab(...)` schedules were sent as Celery's expanded value lists, such as `0 0 1,2,...,31 1,...,12 0,...,6` for a daily job, which exceed the server's 100-character schedule limit, so most Beat tasks were rejected at sync. Each field is now collapsed to `*`, `*/n`, `a-b/n` or a list of values and ranges.
- Interval schedules (`timedelta`, seconds, `schedule(run_every=...)`) were mapped to a guessed cron that ignored when Beat started and fell back to hourly for uncommon intervals, so runs were expected at the wrong times. They and `solar(...)` schedules are now skipped with a warning on stderr.

### Added
- A one-time stderr reminder to set the CronRadar application's time zone when Celery evaluates crontabs outside UTC, and a warning for crontabs with a custom `nowfun`.
